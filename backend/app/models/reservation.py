from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey
from app.models.user import User
from app.models.lab import Lab
from sqlalchemy import String
from app.models.equipment import Equipment
from datetime import datetime
from sqlalchemy import DateTime

class Reservation(Base):
    __tablename__="reservations"
    __table_args__={"comment":"预约信息"}

    user_id: Mapped[int] =mapped_column(ForeignKey("users.id"),comment="预约人",nullable=False)
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), comment="实验室", nullable=False
    )
    equipment_id: Mapped[int | None] = mapped_column(
            ForeignKey("equipments.id"), comment="设备允许为空", nullable=True
        )

    remark:Mapped[str]=mapped_column(String(255),comment="备注",nullable=True)
    reservation_type: Mapped[int] = mapped_column(
        comment="预约类型 0仅实验室 1仅设备 2实验室+设备", default=0
    )
    status: Mapped[int] = mapped_column(comment="预约状态 0待审核 1已通过 2已拒绝 3已取消 4已过期", default=0)

    start_at:Mapped[datetime]=mapped_column(DateTime,comment="预约开始日期时间",nullable=False)
    end_at:Mapped[datetime]=mapped_column(DateTime,comment="预约结束日期时间",nullable=False)

    # 三个关联对象
    user:Mapped[User]=relationship()
    lab: Mapped[Lab] = relationship()
    equipment: Mapped[Equipment] = relationship()
