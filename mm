from typing import Annotated, Optional
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ...core.db.database import async_get_db
from ...core.models.disability import Disability  # Your SQLAlchemy model

# Router without prefix; prefix will be added when included in main router
router = APIRouter(tags=["Register Disability"])


# Request schema
class RegisterDisabilityRequest(BaseModel):
    user_id: int
    disability_getinfor: Optional[str] = None
    disability_family_name: str
    disability_given_name: str
    disability_name: str
    disability_family_name_en: Optional[str] = None
    disability_given_name_en: Optional[str] = None
    disability_name_eng: Optional[str] = None
    gender: int  # 1: Male, 2: Female
    national_id: Optional[str] = None
    family_code: Optional[str] = None
    phone_number: Optional[str] = None
    idpoor_id: Optional[str] = None
    vacine_status: Optional[bool] = None
    vacine_date: Optional[date] = None
    job: Optional[str] = None
    village_id: str
    date_of_birth: date
    live_with_who: str
    reason_disability: str
    created_by: int
    year_start_disability: int
    submit_date: date
    score_question: str
    score_status_live: Optional[bool] = None
    disability_photo: str
    disability_photo_infor: str
    disability_photo_path: str
    disability_photo_doc: Optional[str] = None
    child_education_level: Optional[str] = None
    is_educated: Optional[str] = None
    education_level: Optional[str] = None
    have_income: Optional[str] = None
    primary_job: Optional[str] = None
    find_job: Optional[str] = None
    no_job_reason: Optional[str] = None
    no_job_reason_other: Optional[str] = None
    no_tvet: Optional[str] = None
    is_tvet: Optional[str] = None
    daily_help: Optional[str] = None
    chronic_diseases: Optional[str] = None
    idpoor_status: Optional[str] = None


# Response schema
class RegisterDisabilityResponse(BaseModel):
    id: int
    message: str


@router.post(
    "/register-disability",
    response_model=RegisterDisabilityResponse,
    summary="Register a new disability record"
)
async def register_disability(
    data: RegisterDisabilityRequest,
    authorization: Annotated[str, Header(..., description="Bearer token")],
    db: Annotated[AsyncSession, Depends(async_get_db)]
):
    # Optional: validate Authorization token here
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    # Create new record
    new_disability = Disability(**data.dict())
    db.add(new_disability)
    await db.commit()
    await db.refresh(new_disability)

    return RegisterDisabilityResponse(
        id=new_disability.id,
        message="Disability record registered successfully"
    )
