from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies.auth import get_current_admin, get_current_user
from app.models.user import User
from app.models.lab import Lab
from app.schemas.lab import (
    LabResponse,
    LabUpdateRequest,
    LabCreateRequest
)
from app.common.response import Response
from app.services import lab_services

router = APIRouter(prefix="/lab", tags=["实验室信息接口"])


@router.get("/list")
def get_lab_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    status:int |None=None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = lab_services.get_lab_page_list(db, page, page_size, keywords,status)
    return Response.success(data=res)


@router.get("/{lab_id}")
def get_lab_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = lab_services.get_lab(db,id)
    return Response.success(data=res)


@router.post("")
def create_lab(
    data: LabCreateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_services.create_lab(db, data)
    return Response.success(data=res)


@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    data: LabUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_services.update_lab(db, data, lab_id)
    return Response.success(data=res)


@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lab_services.delete_lab(db, lab_id)
    return Response.success()
