from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user,get_current_admin
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest,ReservationAuditRequest
from app.services import reservation_services

router = APIRouter(prefix="/reservation", tags=["预约相关接口"])


@router.post("")
def create_reservation(data: ReservationCreateRequest, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    reservation_services.create_reservation(db,current_user,data)
    return Response.success()


@router.get("/list")
def get_reservation_page_list(
    page:int =Query(1,ge=1),
    page_size:int=Query(10,ge=1,le=100),
    status:int |None=None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res=reservation_services.get_reservation_page_list(db, current_user, page,page_size,status)
    return Response.success(data=res)


@router.put("/{reservation_id}/cancel")
def cancel_reservation(reservation_id:int, 
                       current_user: User = Depends(get_current_user)
                       ,db: Session = Depends(get_db)):
    reservation_services.cancel_reservation(db,current_user,reservation_id)
    return Response.success(message="预约已取消")


@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,
    data: ReservationAuditRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation_services.audit_reservation(
        db, current_user, reservation_id, data.status
    )
    return Response.success(message="审核完成")
