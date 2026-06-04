import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import datetime
from sqlalchemy import select
from typing import Optional
from fastapi import Query

from ...api.auth_keycloak import get_user_info
from ...core.db.database import async_get_db
from ...core.utils.user_validation import validate_user
from ...schemas.user_keycloak import UserInSignInKeyCloak
from ...schemas.complaint_type import ComplaintTypeCreateInternal
from ...crud.crud_complaint_type import crud_complaint_type
from ...models.main import Main, AccountStatus

from ...schemas.complaint import ComplaintCreate, ComplaintCreateInternal
from ...models.complaint_type import ComplaintTypeTable
from ...models.complaint import ComplaintTable
from ...crud.crud_complaint import crud_complaint
from ...core.utils.helpers import get_asset_url
from ...schemas.complaint import ComplaintListResponse

from fastapi import APIRouter, UploadFile, File, Form, Depends
from datetime import datetime
import uuid
import io
import logging
from typing import Optional

from app.core.services.minio_service import MinioService
from app.models.main import Main
# from ...crud.complaint import crud_complaint

router = APIRouter(tags=["complaint-fraud-view"], prefix="/complaint-fraud-view")

# Complaint and Fraud Type
@router.post(
    "/complaint_type",
    summary="Seed database with complaint and fraud types",
    description="This endpoint inserts all types of complaints and frauds if they do not already exist. Optionally fetch by ID using query parameter `id`.",
)
async def complaint_fraud_type(
    keycloak_user: Annotated[UserInSignInKeyCloak, Depends(get_user_info)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    id: Optional[int] = Query(None, description="Optional ID to fetch a specific complaint/fraud type")
) -> dict:
    logging.info("Authenticated keycloak_user: %s", keycloak_user)
    db_user = await validate_user(keycloak_user.username, keycloak_user, db)
    user_id = db_user["id"]

    # Seed data
    COMPLAINTS_FRAUD_TYPES = [
        {"title": "ប័ណ្ណរកឃើញវិញ", "type": "COMPLAINT"},
        {"title": "បាត់ ឬខូចប័ណ្ណ", "type": "COMPLAINT"},
        {"title": "ជនមានពិការភាពបានស្លាប់", "type": "COMPLAINT"},
        {"title": "ធើ្វបច្ចុប្បន្នភាពពិការភាព", "type": "COMPLAINT"},
        {"title": "ពិការភាពជាសះស្បើយឡើងវិញ", "type": "COMPLAINT"},
        {"title": "ឈ្មោះមិនត្រឹមត្រូវ", "type": "COMPLAINT"},
        {"title": "ភេទមិនត្រឹមត្រូវ", "type": "COMPLAINT"},
        {"title": "ថ្ងៃខែឆ្នាំកំណើតមិនត្រឹមត្រូវ", "type": "COMPLAINT"},
        {"title": "កែតម្រូវអាស័យដ្ឋាន", "type": "COMPLAINT"},
        {"title": "រូបថតលើប័ណ្ណមិនត្រឹមត្រូវ", "type": "COMPLAINT"},
        {"title": "ប្រើប្រាស់ឯកសាររបស់អ្នកដទៃ", "type": "FRAUD"},
        {"title": "ចុះឈ្មោះលើសពីរដង", "type": "FRAUD"},
        {"title": "ផ្តល់ព័ត៏មានមិនត្រឹមត្រូវ", "type": "FRAUD"}
    ]

    # Seed into DB
    for item in COMPLAINTS_FRAUD_TYPES:
        try:
            async with db.begin_nested():
                exists = await crud_complaint_type.check_duplicate_title(db, title=item["title"])
                if exists:
                    continue

                create_data = ComplaintTypeCreateInternal(
                    title=item["title"],
                    type=item["type"],
                    created_by=user_id,
                    updated_by=user_id,
                    submitted_at=datetime.utcnow()
                )
                await crud_complaint_type.create(db=db, object=create_data)
        except Exception:
            await db.rollback()
            continue

    # Fetch by ID if provided
    if id:
        data = await crud_complaint_type.get_by_id(db=db, id=id)
        results = []
        if data:
            results.append({
                "id": data.id,
                "title": data.title,
                "type": data.type,
                "created_by": data.created_by,
                "updated_by": data.updated_by,
                "submitted_at": data.submitted_at,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "deleted_at": data.deleted_at,
                "is_deleted": data.is_deleted
            })
    else:
        all_data = await crud_complaint_type.get_all_active(db=db, limit=1000)
        results = [
            {
                "id": row.id,
                "title": row.title,
                "type": row.type,
                "created_by": row.created_by,
                "updated_by": row.updated_by,
                "submitted_at": row.submitted_at,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "deleted_at": row.deleted_at,
                "is_deleted": row.is_deleted
            }
            for row in all_data
        ]

    return {
        "message": "Complaint and fraud types seeding completed",
        "status": "success",
        "data": results
    }


# Get all Accountstatus
@router.get(
    "/all",
    summary="Get all account status values",
    description="Returns all possible account status values as defined in the system"
)
async def get_all_account_status(
    keycloak_user: Annotated[UserInSignInKeyCloak, Depends(get_user_info)]
):
    """
    Fetch all account status values (full words) from the AccountStatus enum.
    """
    logging.info("Authenticated user: %s", keycloak_user.username)

    # Return all enum values as a list
    statuses = [status.name for status in AccountStatus]

    return {
        "error": False,
        "message": "All account status values retrieved successfully",
        "data": statuses
    }


# Manage info part
@router.post(
    "/complaints",
    summary="Create Complaint",
    response_model=None
)
async def create_complaint(
    keycloak_user: Annotated[UserInSignInKeyCloak, Depends(get_user_info)],
    db: Annotated[AsyncSession, Depends(async_get_db)],
    disability_card: str = Form(...),
    disability_address: Optional[str] = Form(None),
    case_type: Optional[str] = Form(None),
    complainant_name: Optional[str] = Form(None),
    complainant_relation: Optional[str] = Form(None),
    receiver_name: Optional[str] = Form(None),
    receiver_position: Optional[str] = Form(None),
    complaint_type_id: Optional[int] = Form(None),
    is_disability: Optional[str] = Form(None),
    correct_value: Optional[str] = Form(None),
    complaint_image: UploadFile = File(...),
):
    try:
        logging.info("Authenticated user: %s", keycloak_user.username)
        db_user = await validate_user(keycloak_user.username, keycloak_user, db)
        user_id = db_user["id"]

        # --- Convert form string to boolean ---
        is_disability_bool = False
        if is_disability is not None:
            if isinstance(is_disability, str):
                is_disability_bool = is_disability.lower() == "true"
            elif isinstance(is_disability, bool):
                is_disability_bool = is_disability

        # --- Fetch disability name if applicable ---
        disability_name = None
        if is_disability_bool:
            if not disability_card:
                return {"error": True, "message": "disability_card is required when is_disability is True"}

            if len(disability_card) > 100:
                return {"error": True, "message": "លេខបណ្ណ័ពិការភាពមិនត្រឹមត្រូវ"}

            stmt = select(Main).where(Main.disability_code == disability_card)
            result = await db.execute(stmt)
            main_record = result.scalar_one_or_none()
            if not main_record:
                return {"error": True, "message": f"លេខបណ្ណ័ពិការភាព {disability_card} មិនមានក្នុងទិន្នន័យ"}

            disability_name = " ".join(filter(None, [main_record.family_name, main_record.given_name]))

            logging.info("Fetched disability_name: %s", disability_name)

        # --- Validate complaint type ---
        complaint_type = None
        if complaint_type_id is not None:
            stmt = select(ComplaintTypeTable).where(
                ComplaintTypeTable.id == complaint_type_id,
                ComplaintTypeTable.is_deleted == False
            )
            result = await db.execute(stmt)
            complaint_type = result.scalar_one_or_none()
            if not complaint_type:
                return {"error": True, "message": "លេខសម្គាល់ ប្រភេទបណ្តឹងតវ៉ា ឬប្រភេទក្លែងបន្លំមិនត្រឹមត្រូវ"}

        # --- Check for duplicate complaint ---
        stmt_check = select(ComplaintTable).where(
            ComplaintTable.disability_card == disability_card,
            ComplaintTable.case_type == case_type
        )
        result_check = await db.execute(stmt_check)
        existing_complaint = result_check.scalar_one_or_none()
        if existing_complaint:
            return {"error": True, "message": "ទិន្ន័យមានរួចហើយ"}

        # --- Read and upload file ---
        content = await complaint_image.read()
        unique_id = str(uuid.uuid4())
        file_extension = complaint_image.filename.split(".")[-1]
        file_path = f"complaints/{unique_id}.{file_extension}"

        await MinioService.upload_file(
            file_content=content,
            file_name=file_path,
            content_type=complaint_image.content_type
        )

        # --- Prepare complaint object ---
        complaint_internal = ComplaintCreateInternal(
            disability_card=disability_card,
            disability_address=disability_address,
            case_type=case_type,
            complainant_name=complainant_name,
            complainant_relation=complainant_relation,
            receiver_name=receiver_name,
            receiver_position=receiver_position,
            complaint_type_id=complaint_type_id,
            is_disability=is_disability_bool,
            correct_value=correct_value,
            complaint_image=file_path,
            disability_name=disability_name,
            created_by=user_id,
            updated_by=user_id,
            submitted_at=datetime.utcnow()
        )

        # --- Save to DB ---
        created = await crud_complaint.create(db=db, object=complaint_internal)
        await db.commit()
        await db.refresh(created)

        # --- Generate accessible URL ---
        image_url = get_asset_url(created.complaint_image, keycloak_user.token)

        return {
            "error": False,
            "message": "Complaint created successfully",
            "data": {
                "id": created.id,
                "disability_card": created.disability_card,
                "disability_name": disability_name,
                "complaint_image": image_url,
                "correct_value": created.correct_value,
                "case_type": created.case_type,
                "complainant_name": created.complainant_name,
                "complainant_relation": created.complainant_relation,
                "receiver_name": created.receiver_name,
                "receiver_position": created.receiver_position,
                "complaint_type_id": created.complaint_type_id,
                "is_disability": created.is_disability,
            }
        }

    except Exception as e:
        await db.rollback()
        logging.error("Error creating complaint: %s", str(e))
        return {"error": True, "message": "Internal server error"}


# List All Complaint and Filter
@router.get(
    "/get_complaints",
    summary="List complaints with filters",
    response_model=ComplaintListResponse
)
async def list_complaints(
    keycloak_user: Annotated[UserInSignInKeyCloak, Depends(get_user_info)],
    db: Annotated[AsyncSession, Depends(async_get_db)],

    disability_name: Optional[str] = Query(None),
    case_type: Optional[str] = Query(None),
    complainant_name: Optional[str] = Query(None),
    receiver_name: Optional[str] = Query(None),
    receiver_position: Optional[str] = Query(None),
    created_by: Optional[int] = Query(None),
):
    try:
        logging.info("Authenticated user: %s", keycloak_user.username)

        # Validate user
        db_user = await validate_user(keycloak_user.username, keycloak_user, db)

        if created_by is None:
            created_by = db_user["id"]

        complaints = await crud_complaint.filter_complaints(
            db=db,
            disability_name=disability_name,
            case_type=case_type,
            complainant_name=complainant_name,
            receiver_name=receiver_name,
            receiver_position=receiver_position,
            created_by=created_by
        )

        return {
            "error": False,
            "message": "Success",
            "data": complaints
        }

    except Exception as e:
        logging.error("Error listing complaints: %s", str(e))
        return {
            "error": True,
            "message": "Internal server error",
            "data": []
        }
