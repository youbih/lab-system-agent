from app.models.lab import Lab
from app.schemas.lab import LabResponse
from sqlalchemy.orm import Session
from app.schemas.lab import LabUpdateRequest, LabCreateRequest, LabResponse

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from sqlalchemy import or_


def get_lab_page_list(
    db: Session, page: int, page_size: int, keywords: str | None = None,status:int |None=None
):
    # select * from lab where name like "计算机实验室"
    query = db.query(Lab)
    if keywords:
        query =query.filter(Lab.name.ilike(f"%{keywords}%"))
    if status:
        query=query.filter(Lab.status==status)
    total = query.count()
    items = (
        query.order_by(Lab.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )

def get_lab(db:Session,lab_id:int):
    lab=db.query(Lab).filter(Lab.id==lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    return LabResponse.model_validate(lab)
    

def create_lab(db: Session, data: LabCreateRequest):
    """新增"""
    exist = db.query(Lab).filter(Lab.name == data.name).first()
    if exist:
        raise BusinessException(message="实验室已存在")

    lab=Lab(**data.model_dump())

    db.add(lab)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, data: LabUpdateRequest, lab_id: int):
    """更新"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")

    # 更新名称时，检查是否与其他实验室重名
    if data.name is not None:
        exist = db.query(Lab).filter(Lab.name == data.name, Lab.id != lab_id).first()

        if exist:
            raise BusinessException(message="实验室已存在")

    payload = data.model_dump(exclude_none=True)
    for filed, value in payload.items():
        setattr(lab, filed, value)

    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def delete_lab(db: Session, lab_id: int):
    """删除"""
    
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    db.delete(lab)
    db.commit()
