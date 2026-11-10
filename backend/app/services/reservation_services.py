from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest

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

    # 5. 选了设备时，检查设备存在、归属和状态
    if data.equipment_id is not None:
        equipment = (
            db.query(Equipment).filter(Equipment.id == data.equipment_id).first()
        )

        if not equipment:
            raise BusinessException(message="实验室设备不存在")

        if equipment.lab_id != data.lab_id:
            raise BusinessException(message="该设备不属于所选实验室")

        if equipment.status != 1:
            raise BusinessException(message="实验室设备正在维修")

    # 6. 使用完整日期时间判断预约冲突
    query = db.query(Reservation).filter(
        Reservation.lab_id == data.lab_id,
        Reservation.status.in_([0, 1]),
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    )

    if data.equipment_id is not None:
        query = query.filter(Reservation.equipment_id == data.equipment_id)
    else:
        query = query.filter(Reservation.equipment_id.is_(None))

    if query.first():
        raise BusinessException(message="该时段已预约")

    # 7. 保存预约
    reservation = Reservation(
        user_id=current_user.id,
        lab_id=data.lab_id,
        equipment_id=data.equipment_id,
        start_at=start_at,
        end_at=end_at,
        remark=data.remark,
        status=0,
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)
