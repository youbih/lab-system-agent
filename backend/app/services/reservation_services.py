from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from app.common.response import PageResponse
from app.common.exceptions import BusinessException
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse

"""
预约顺序解析：

1. 解析完整的开始、结束日期时间。
2. 检查结束时间晚于开始时间。
3. 检查开始时间至少提前 1 小时、最多提前 7 天。
4. 检查实验室存在、开放，整个预约区间符合开放规则。
5. 检查设备存在、归属和状态。
6. 使用完整日期时间检查预约冲突。
7. 保存预约

"""

# 北京时间
TIMEZONE=ZoneInfo("Asia/Shanghai")

# 将任意一个时刻的时间转换为北京时间
def to_beijing_time(value: datetime) -> datetime:
    """统一转换为不带时区信息的北京时间。"""
    if value.tzinfo is not None:
        return value.astimezone(TIMEZONE).replace(tzinfo=None)

    # 前端没有携带时区时，约定输入的就是北京时间
    return value


def check_opening_hours(
    lab: Lab,
    start_at: datetime,
    end_at: datetime,
):
    """检查整个预约区间是否位于连续开放时段内。"""
    if not lab.open_time or not lab.close_time:
        raise BusinessException(message="实验室尚未配置完整的开放时间")

    try:
        open_time = datetime.strptime(lab.open_time, "%H:%M").time()
        close_time = datetime.strptime(lab.close_time, "%H:%M").time()
    except ValueError:
        raise BusinessException(message="实验室开放时间配置格式错误")

    # 约定 00:00—00:00 表示全天开放
    if open_time == time(0, 0) and close_time == time(0, 0):
        return

    if open_time == close_time:
        raise BusinessException(message="实验室开放时间配置无效")

    if open_time < close_time:
        # 白天开放，例如当天 08:00—22:00
        window_start = datetime.combine(start_at.date(), open_time)
        window_end = datetime.combine(start_at.date(), close_time)
    else:
        # 夜间开放，例如当天 20:00—次日 08:00
        window_start = datetime.combine(start_at.date(), open_time)
        window_end = datetime.combine(
            start_at.date() + timedelta(days=1),
            close_time,
        )

        # 凌晨预约属于前一天晚上开始的开放时段
        if start_at.time() < close_time:
            window_start -= timedelta(days=1)
            window_end -= timedelta(days=1)

    if start_at < window_start or end_at > window_end:
        raise BusinessException(message="整个预约区间必须处于实验室的连续开放时段内")


def create_reservation(
    db: Session,
    current_user: User,
    data: ReservationCreateRequest,
):
    """创建预约记录。"""

    # 1. schema 已经完成解析，这里统一时区
    start_at = to_beijing_time(data.start_at)
    end_at = to_beijing_time(data.end_at)
    if data.reservation_type not in (0, 1, 2):
        raise BusinessException(message="无效的预约类型")
    if data.reservation_type == 0 and data.equipment_id is not None:
        raise BusinessException(message="仅预约实验室时不能选择设备")
    if data.reservation_type in (1, 2) and data.equipment_id is None:
        raise BusinessException(message="该预约类型必须选择设备")

    # 日期以转换后的北京时间为准
    if start_at.date() != end_at.date():
        raise BusinessException(message="暂不支持跨天预约，请选择同一天的时间")

    if end_at <= start_at:
        raise BusinessException(message="预约结束时间必须晚于开始时间")

    # 开始、结束都必须是整点或半点，且不能携带秒和微秒
    for value in (start_at, end_at):
        if value.minute not in (0, 30) or value.second != 0 or value.microsecond != 0:
            raise BusinessException(message="预约时间只能选择整点或半点，秒必须为0")

    if end_at - start_at < timedelta(minutes=30):
        raise BusinessException(message="单次预约至少30分钟")

    # 3. 开始时间必须至少提前1小时，最多提前7天
    now = datetime.now(TIMEZONE).replace(tzinfo=None)

    if start_at < now + timedelta(hours=1):
        raise BusinessException(message="请至少提前1小时预约")

    if start_at > now + timedelta(days=7):
        raise BusinessException(message="最多只能提前7天预约")

    # 4. 检查实验室及整个预约区间的开放情况
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()

    if not lab:
        raise BusinessException(message="实验室不存在")

    if lab.status != 1:
        raise BusinessException(message="实验室已关闭")

    check_opening_hours(lab, start_at, end_at)

    # 5. 仅设备/实验室+设备时，校验设备存在、归属和状态
    if data.reservation_type in (1,2):
        equipment = (
            db.query(Equipment).filter(Equipment.id == data.equipment_id).first()
        )

        if not equipment:
            raise BusinessException(message="实验室设备不存在")

        if equipment.lab_id != data.lab_id:
            raise BusinessException(message="该设备不属于所选实验室")

        if equipment.status != 1:
            raise BusinessException(message="实验室设备正在维修")

    # 占用实验室的类型：0、2
    if data.reservation_type in (0, 2):
        exists = (
            db.query(Reservation)
            .filter(
                Reservation.lab_id == data.lab_id,
                Reservation.reservation_type.in_([0, 2]),  # 只有占实验室的记录才冲突
                Reservation.status.in_([0, 1]),  # 待审核+已通过才算占用
                Reservation.start_at < end_at,  # 时间重叠的标准写法
                Reservation.end_at > start_at,
            )
            .first()
        )
        if exists:
            raise BusinessException(message="该时段实验室已被预约")

    # 占用设备的类型：1、2
    if data.reservation_type in (1, 2):
        exists = (
            db.query(Reservation)
            .filter(
                Reservation.equipment_id == data.equipment_id,
                Reservation.reservation_type.in_([1, 2]),  # 只有占设备的记录才冲突
                Reservation.status.in_([0, 1]),
                Reservation.start_at < end_at,
                Reservation.end_at > start_at,
            )
            .first()
        )
        if exists:
            raise BusinessException(message="该设备在该时段已被预约")

    # 7. 保存预约
    reservation = Reservation(
        user_id=current_user.id,
        lab_id=data.lab_id,
        equipment_id=data.equipment_id,
        start_at=start_at,
        end_at=end_at,
        remark=data.remark,
        status=0,
        reservation_type=data.reservation_type
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)


def get_reservation_page_list(db:Session,current_user:User,page:int,page_size:int,status:int | None=None):
    """查询预约的记录"""
    query=db.query(Reservation)
    if current_user.role!="admin":
        query=query.filter(Reservation.user_id==current_user.id)
    if status is not None:
        query=query.filter(Reservation.status==status)
    total=query.count()
    items = (
        query.options(
            joinedload(Reservation.user),
            joinedload(Reservation.lab),
            joinedload(Reservation.equipment),
        )
        .order_by(Reservation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    result=[]
    for item in items:
        res=ReservationResponse.model_validate(item)
        res.user_name =item.user.name if item.user else None
        res.lab_name=item.lab.name if item.lab else None
        res.equipment_name=item.equipment.name if item.equipment else None
        result.append(res)

    return PageResponse(list=result,total=total)


def cancel_reservation(db:Session,current_user:User,reservation_id:int):
    """学生取消自己的待审核预约"""
    item = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,  # 找到"我说要取消的那条预约"
            Reservation.user_id == current_user.id,  # 并且这条预约必须是我订的
        )
        .first()
    )
    if not item:
        raise BusinessException(message="预约记录不存在或无权操作")

    if item.status == 3:
        raise BusinessException(message="该预约已取消，请勿重复操作")

    if item.status != 0:
        raise BusinessException(message="只有待审核的预约可以取消")

    item.status = 3
    db.commit()


def audit_reservation(
    db: Session, current_user: User, reservation_id: int, status: int
):
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not item:
        raise BusinessException(message="预约记录不存在")

    if status not in (1, 2):
        raise BusinessException(message="无效的审核结果")

    if item.status != 0:
        raise BusinessException(message="只有待审核的预约可以审核")

    item.status = status
    db.commit()
