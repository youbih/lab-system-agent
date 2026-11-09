from sqlalchemy.orm import Session, joinedload

from app.common.exceptions import BusinessException
from app.common.response import PageResponse
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentResponse,
    EquipmentUpdateRequest,
)


def _get_lab(db: Session, lab_id: int) -> Lab:
    """新增或更新设备前，确认所属实验室存在。"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    return lab


def _to_equipment_response(equipment: Equipment) -> EquipmentResponse:
    """设备模型没有lab_name属性，需要从lab关联中补充实验室名称。"""
    result = EquipmentResponse.model_validate(equipment)
    result.lab_name = equipment.lab.name if equipment.lab else None
    return result


def get_equipment_page_list(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None,
    lab_id: int | None = None,
):
    """分页查询设备，可按设备名称和所属实验室筛选。"""
    query = db.query(Equipment)
    if keywords:
        query = query.filter(Equipment.name.ilike(f"%{keywords}%"))
    if lab_id is not None:
        query = query.filter(Equipment.lab_id == lab_id)

    total = query.count()
    items = (
        # 一起读取所属实验室，避免为每一条设备单独查询实验室名称。
        query.options(joinedload(Equipment.lab))
        .order_by(Equipment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[_to_equipment_response(item) for item in items], total=total
    )


def create_equipment(db: Session, data: EquipmentCreateRequest):
    """新增设备，同一实验室内不允许设备名称重复。"""
    lab = _get_lab(db, data.lab_id)
    exist = (
        db.query(Equipment)
        .filter(Equipment.lab_id == data.lab_id, Equipment.name == data.name)
        .first()
    )
    if exist:
        raise BusinessException(message="该实验室中已存在同名设备")

    equipment = Equipment(**data.model_dump())
    equipment.lab = lab

    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    return _to_equipment_response(equipment)


def update_equipment(db: Session, data: EquipmentUpdateRequest, equipment_id: int):
    """更新设备，更换实验室或名称时检查最终组合是否重名。"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="设备不存在")

    payload = data.model_dump(exclude_none=True)
    target_lab_id = payload.get("lab_id", equipment.lab_id)
    target_name = payload.get("name", equipment.name)
    lab = _get_lab(db, target_lab_id)

    # 排除设备自身：不修改名称或实验室时，不应误判为重复。
    exist = (
        db.query(Equipment)
        .filter(
            Equipment.lab_id == target_lab_id,
            Equipment.name == target_name,
            Equipment.id != equipment_id,
        )
        .first()
    )
    if exist:
        raise BusinessException(message="该实验室中已存在同名设备")

    for field, value in payload.items():
        setattr(equipment, field, value)
    # 同步关联对象，确保更换实验室后返回的新lab_name正确。
    equipment.lab = lab

    db.commit()
    db.refresh(equipment)
    return _to_equipment_response(equipment)


def delete_equipment(db: Session, equipment_id: int):
    """删除设备，不存在时返回业务异常。"""
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise BusinessException(message="设备不存在")
    db.delete(equipment)
    db.commit()
