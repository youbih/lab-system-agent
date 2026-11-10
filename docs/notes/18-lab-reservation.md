# 开发实验室预约功能

> 对应课程：第 18 节
> 对应项目：`agent-lab/lab-system-agent`
> 前置课程：第 15 节实验室管理、第 16 节设备管理、第 17 节学生端实验室与设备列表
> 最终版本：同日预约、半小时刻度、至少提前 1 小时、最多提前 7 天
> 下一课：第 19 节，开发我的预约和预约审核
> 整理日期：2026-11-10
> 阅读方式：按“代码做什么 → 每一步为什么这样写 → 用户操作后发生什么”理解。

---

## 第零章 这节课完成了什么

第 17 节的“预约”按钮只显示“预约功能开发中”。本节把两个入口都接到了真实的预约接口：学生可以预约实验室本身，也可以预约某个实验室中的设备。

本课完成的是**创建一条待审核的预约**。返回成功表示提交成功，`status=0`；不表示管理员已经通过，也没有实现“我的预约”列表、取消预约或预约审核界面。这些内容在下一课继续开发。

### 0.1 最终规则，复习时先看这里

| 检查 | 最终要求 |
|---|---|
| 日期 | 开始和结束必须是同一个北京时间日期，暂不支持跨天 |
| 时间刻度 | 开始、结束只能在整点或半点，秒和微秒都必须为 0 |
| 时长 | 至少 30 分钟；因此有效时长是 30 分钟的整数倍 |
| 提前时间 | `当前时间 + 1小时 ≤ 开始时间 ≤ 当前时间 + 7天` |
| 实验室 | 存在、状态开放，整个预约区间都位于连续开放时段内 |
| 设备 | 如果选择设备，设备必须存在、属于所选实验室、状态正常 |
| 冲突 | 同一预约对象存在时间重叠的待审核或已通过记录时，拒绝创建 |
| 预约人 | 由 token 对应的当前登录用户决定，不接受前端指定预约人 |
| 新记录状态 | 一律待审核，`status=0` |

“最多提前 7 天”按开始时刻计算，是滚动的 168 小时，不是简单允许选择日历上的第七天全天。“至少提前 1 小时”也以服务器处理请求时的当前时间为准。

例如当前是 10:10，提前一小时后的时刻是 11:10，最早能选的半小时刻度就是 11:30。前端选择时满足要求，并不意味着等很久再提交仍满足，所以提交时需要重新校验，后端也要独立判断。

### 0.2 本节涉及哪些文件

| 文件 | 本课承担的作用 |
|---|---|
| `backend/app/models/reservation.py` | 定义预约表、字段及用户/实验室/设备关联 |
| `backend/app/schemas/reservation.py` | 定义创建请求，把日期时间字符串解析为 `datetime` |
| `backend/app/services/reservation_services.py` | 实现时间、资源、冲突检查并保存 |
| `backend/app/api/reservation.py` | 定义 `POST /api/reservation`，获取当前用户并调用 service |
| `backend/app/api/__init__.py` | 注册预约 router |
| `backend/app/main.py` | 导入预约模型，使表模型进入 metadata |
| `frontend/src/api/reservation.js` | 封装创建预约的 HTTP 请求 |
| `frontend/src/components/ReserveDialog.vue` | 共用预约弹窗：展示、选择、校验、提交、关闭与重置 |
| `frontend/src/views/LabList.vue` | 点击实验室的预约按钮，传入实验室信息 |
| `frontend/src/views/LabEquipment.vue` | 点击设备的预约按钮，传入实验室和设备信息 |

本节没有新增预约页面路由。已有的两个页面复用弹窗；因此不需要给 `ReserveDialog.vue` 单独配置 Vue Router。

### 0.3 一次预约如何流转

```text
学生在实验室/设备列表点击“预约”
    ↓
父页面保存所选对象，打开 ReserveDialog
    ↓
选择预约日期、开始时间、结束时间，填写可选备注
    ↓
前端 validate 校验，并把日期和时间拼成 start_at/end_at
    ↓
createReservationApi → Axios 附带 token → POST /api/reservation
    ↓
FastAPI 解析请求，验证当前登录用户
    ↓
service 校验日期、半小时刻度、提前时间、开放情况、设备及冲突
    ↓
写入 reservations，预约人来自 current_user.id，状态为 0
    ↓
返回成功，前端提示“请等待审核”，关闭并重置表单
```

---

## 第一章 后端模型：一条预约保存哪些信息

### 1.1 Reservation 数据表模型

```python
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
    status: Mapped[int] = mapped_column(comment="预约状态 0待审核 1已通过 2已拒绝 3已取消", default=0)

    start_at:Mapped[datetime]=mapped_column(DateTime,comment="预约开始日期时间",nullable=False)
    end_at:Mapped[datetime]=mapped_column(DateTime,comment="预约结束日期时间",nullable=False)

#三个关联对象
    user:Mapped[User]=relationship()
    lab: Mapped[Lab] = relationship()
    equipment: Mapped[Equipment] = relationship()
```

逐组理解：

1. `__tablename__ = "reservations"` 指定数据库表名。
2. `user_id`、`lab_id` 分别指向预约人、所属实验室，这两个外键必须有值。
3. `equipment_id` 允许 `None/NULL`：没有设备 ID 表示预约实验室本身，有设备 ID 表示预约该设备。
4. `start_at`、`end_at` 使用数据库的 `DATETIME`，同时保存年、月、日、时、分、秒。
5. `remark` 保存备注；数据库配置为可空。
6. `status` 保存预约状态，而不是实验室或设备的状态。
7. `user`、`lab`、`equipment` 是 ORM 关联对象，方便以后从预约读取关联信息。它们不是重复存储的名字字段。

模型没有显式声明 `id`，因为 `Base` 已统一声明自增主键，以及 `create_time`、`update_time`。子模型会继承这些公共列。

| 预约状态值 | 含义 | 当前冲突检查是否计入 |
|---|---|---|
| `0` | 待审核 | 是 |
| `1` | 已通过 | 是 |
| `2` | 已拒绝 | 否 |
| `3` | 已取消 | 否 |

预约状态 `0` 的意思与实验室状态 `0=关闭`、设备状态 `0=维修` 不一样，要结合所属模型理解。

### 1.2 为什么不再单独保存 date

旧结构是 `date + start_time + end_time`，三个字段都是字符串。当前结构改成两个完整日期时间：

```text
start_at = 2026-11-12 09:00:00
end_at   = 2026-11-12 10:30:00
```

这两个值已经包含日期，所以后端不需要额外的 `date` 字段。即使最终取消跨天预约，也可以保留完整日期时间结构，只通过业务校验限制开始、结束在同一天，不用把数据库再迁回去。

注意：表单里仍有 `form.date`，那只是方便用户填写的前端状态，不意味着后端请求或数据库也必须有同名字段。

---

## 第二章 请求 schema：先把输入变成可处理的数据

```python
from pydantic import BaseModel
from datetime import datetime

class ReservationCreateRequest(BaseModel):
    lab_id:int
    equipment_id:int|None=None
    # start_at 和 end_at 的类型是 datetime，包含完整的日期和时间：年、月、日、时、分、秒
    start_at: datetime
    end_at: datetime
    remark:str |None=None
```

| 请求字段 | 类型 | 为什么这样定义 |
|---|---|---|
| `lab_id` | `int` | 实验室预约和设备预约都需要明确所属实验室 |
| `equipment_id` | `int | None = None` | 允许不选设备；省略或传 `null` 都表示只预约实验室 |
| `start_at`、`end_at` | `datetime` | 让 Pydantic 负责解析完整日期时间 |
| `remark` | 可选字符串 | 没写备注也能提交 |

请求示例（时间只是格式示例，运行时应改成未来 7 天内的有效时间）：

```json
{
  "lab_id": 3,
  "equipment_id": null,
  "start_at": "2026-11-12T09:00:00",
  "end_at": "2026-11-12T10:30:00",
  "remark": "课程实验"
}
```

`T` 是日期和时间之间的分隔符。请求经过 schema 后，service 读取到的 `data.start_at` 已是 Python `datetime`，可以直接比较日期、分钟和时间差，不再是普通字符串。

schema 负责数据结构和类型；“必须同日”“至少提前 1 小时”等业务要求放在 service 中。请求缺字段、日期格式无法解析等情况会返回 HTTP 422，通常不会进入 service。

本节曾出现字段不一致：schema 仍声明 `start_time/end_time`，service 却读取 `start_at/end_at`。正确做法是同步 schema、model、service 和前端请求，而不是只修改字段类型。

---

## 第三章 Service 第一步：统一时区

文件：`backend/app/services/reservation_services.py`。

```python
TIMEZONE=ZoneInfo("Asia/Shanghai")

# 将任意一个时刻的时间转换为北京时间
def to_beijing_time(value: datetime) -> datetime:
    """统一转换为不带时区信息的北京时间。"""
    if value.tzinfo is not None:
        return value.astimezone(TIMEZONE).replace(tzinfo=None)

    # 前端没有携带时区时，约定输入的就是北京时间
    return value
```

`to_beijing_time()` 是我们自己写的辅助函数，作用是让所有后续比较使用同一种时间含义。

逐步执行：

1. 如果输入携带时区，例如 `2026-11-12T01:00:00Z`，先用 `astimezone()` 转成北京时间 09:00。
2. 再用 `replace(tzinfo=None)` 去掉时区标记，按约定保存成普通的北京时间。
3. 如果输入没有时区，例如前端拼出的 `2026-11-12T09:00:00`，直接约定它就是北京时间。

不能把带时区的 UTC 值直接去掉时区，那会把 01:00 错当成北京时间 01:00。这里先转换、后去标记，顺序不能颠倒。

数据库的 `DATETIME` 本身不记录时区。因此“保存不带时区的北京时间”是项目约定；读取和显示时也应保持这个约定。

---

## 第四章 Service 时间规则：同日、半小时、提前时间

### 4.1 create_reservation 的入口

```python
def create_reservation(
    db: Session,
    current_user: User,
    data: ReservationCreateRequest,
):
    start_at = to_beijing_time(data.start_at)
    end_at = to_beijing_time(data.end_at)
```

三个参数分别是：数据库会话、已经通过 token 验证的当前用户、schema 解析后的预约请求。service 不负责从请求头解密 token，api 的依赖已经完成这一步。

### 4.2 同一天且结束晚于开始

```python
# 日期以转换后的北京时间为准
    if start_at.date() != end_at.date():
        raise BusinessException(message="暂不支持跨天预约，请选择同一天的时间")

    if end_at <= start_at:
        raise BusinessException(message="预约结束时间必须晚于开始时间")
```

`start_at.date()` 只取日期部分。先检查两端日期相同，再判断结束是否晚于开始。

| 开始 | 结束 | 结果 |
|---|---|---|
| 11 月 12 日 09:00 | 11 月 12 日 10:00 | 继续检查 |
| 11 月 12 日 10:00 | 11 月 12 日 10:00 | 拒绝，时长为 0 |
| 11 月 12 日 10:00 | 11 月 12 日 09:00 | 拒绝，结束早于开始 |
| 11 月 12 日 23:30 | 11 月 13 日 00:30 | 拒绝，跨天 |

这里检查的是转换后的北京时间日期，而不是原始 JSON 字符串中的日期片段。

### 4.3 半小时刻度和最短时长

```python
# 开始、结束都必须是整点或半点，且不能携带秒和微秒
    for value in (start_at, end_at):
        if value.minute not in (0, 30) or value.second != 0 or value.microsecond != 0:
            raise BusinessException(message="预约时间只能选择整点或半点，秒必须为0")

    if end_at - start_at < timedelta(minutes=30):
        raise BusinessException(message="单次预约至少30分钟")
```

`for value in (start_at, end_at)` 表示对开始、结束两端都检查一次：

- 分钟必须是 `0` 或 `30`；09:10、10:45 不允许。
- 秒和微秒都必须是 0；09:00:01 也不允许。
- `end_at - start_at` 得到 `timedelta`，与 30 分钟比较。

两端都是半小时刻度、且结束晚于开始时，正时长自然是 30 分钟的整数倍。最后的最短时长检查仍明确表达了业务规则。

如果请求是 09:00—09:15，当前代码先发现结束时间不是半小时刻度，因此首先提示刻度错误，不一定出现“至少 30 分钟”。多个条件都不满足时，代码中先执行的检查决定第一条提示。

### 4.4 至少提前 1 小时，最多提前 7 天

```python
# 3. 开始时间必须至少提前1小时，最多提前7天
    now = datetime.now(TIMEZONE).replace(tzinfo=None)

    if start_at < now + timedelta(hours=1):
        raise BusinessException(message="请至少提前1小时预约")

    if start_at > now + timedelta(days=7):
        raise BusinessException(message="最多只能提前7天预约")
```

`datetime.now(TIMEZONE)` 显式取得北京时间，避免依赖服务器默认时区。`now` 只取一次，使两个边界依据同一个时刻计算。

| 判断 | 不满足时的提示 |
|---|---|
| 开始时间小于 `now + 1小时` | 请至少提前 1 小时预约 |
| 开始时间大于 `now + 7天` | 最多只能提前 7 天预约 |

代码使用 `<` 和 `>`，因此数学上恰好 1 小时、恰好 7 天允许。最终还要满足半小时刻度。网络请求有耗时，手动 curl 很难精确命中边界；边界验证应固定当前时间单独检查。

“不能预约过去”已经包含在“至少提前 1 小时”中，不用再分开比较今天日期、当前时分和结束时分。以前用 `strftime("%H-%M")` 得到 `09-30`，与输入 `09:30` 格式不同，现在也不再需要这类字符串比较。

---

## 第五章 Service 资源检查：实验室和设备能不能预约

### 5.1 实验室是否存在、是否开放

```python
# 4. 检查实验室及整个预约区间的开放情况
    lab = db.query(Lab).filter(Lab.id == data.lab_id).first()

    if not lab:
        raise BusinessException(message="实验室不存在")

    if lab.status != 1:
        raise BusinessException(message="实验室已关闭")

    check_opening_hours(lab, start_at, end_at)
```

`db.query(Lab).filter(Lab.id == data.lab_id).first()` 的意思是按 ID 找实验室，找不到返回 `None`，找到返回一个 `Lab` 对象。

查到实验室不表示可以预约，还要检查 `lab.status == 1`。前端按钮禁用只是界面提示，后端必须独立验证，因为 curl 同样能调用接口。

接下来把实验室对象和完整预约区间传给 `check_opening_hours()`。

### 5.2 整个时段都必须处于开放区间

```python
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
```

这个函数可以分为四步理解：

1. 开放时间配置缺失、格式错误时，拒绝预约，不把“未设置”默认为全天开放。
2. 约定 `00:00—00:00` 表示全天开放；其他相等的开始、结束时间视为无效配置。
3. 把每天的开放时分与预约日期组合，得到一个完整的连续开放窗口 `window_start/window_end`。
4. 开始不能早于窗口开始，结束不能晚于窗口结束；刚好在开放时开始、关闭时结束可以。

例如 `08:00—22:00`，预约日期为 11 月 12 日：

```text
window_start = 11月12日 08:00
window_end   = 11月12日 22:00

09:00—10:30 → 在窗口内
07:30—09:00 → 开始太早
21:30—22:30 → 结束太晚
```

**为什么现在禁止跨天，函数中还保留夜间开放的分支？**

“实验室每天夜间开放”和“一条预约跨越两个日期”是不同的事。`20:00—08:00` 表示一个夜间开放窗口，学生仍可以在同一天预约 01:00—02:00，或者 20:00—21:00；但不能提交今天 23:30 到明天 00:30。

如果预约开始于凌晨，应该归到前一晚开始的开放窗口，所以代码把窗口两端都减去一天。例如 11 月 12 日 01:00 对应的窗口是 11 月 11 日 20:00 到 11 月 12 日 08:00。

当前管理端开放时间表单的校验仍主要面向白天开放，是否开放夜间/全天的配置入口属于课程结束后统一整理的前后端一致性事项。本节没有顺带修改管理页面。

### 5.3 只有选择设备时，才做设备检查

```python
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
```

`is not None` 表示明确判断是否提交了设备 ID，不会把 `0` 当成“未选择”；如果传了无效 ID，就按设备不存在处理。

选了设备后依次检查：

```text
设备是否存在
    ↓
equipment.lab_id 是否等于本次 data.lab_id
    ↓
设备 status 是否为 1
```

第二步很重要：设备存在，并不代表属于用户提交的实验室。否则可以把 A 实验室的设备与 B 实验室 ID 拼在一起提交。

三个判断都放在 `if data.equipment_id is not None:` 内。只预约实验室时不需要读取设备，也不会使用尚未赋值的 `equipment` 变量。

---

## 第六章 冲突查询：不是 ID 重复就表示已预约

### 6.1 构建查询，再逐步缩小范围

```python
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
```

`query` 是 SQLAlchemy 的 ORM 查询对象，不是查询结果列表。可以理解为一份正在不断补充条件的查询。

先添加四组条件：

| 条件 | 含义 |
|---|---|
| `Reservation.lab_id == data.lab_id` | 属于同一个实验室 |
| `Reservation.status.in_([0, 1])` | 只考虑待审核或已通过的预约 |
| `Reservation.start_at < end_at` | 已有预约开始早于本次结束 |
| `Reservation.end_at > start_at` | 已有预约结束晚于本次开始 |

这些条件是 AND 关系，必须同时满足。字段左边的 `Reservation.xxx` 指已有记录的列；右边的 `start_at/end_at` 指本次请求统一时区后的值。

接着区分预约对象：

```python
if data.equipment_id is not None:
    query = query.filter(
        Reservation.equipment_id == data.equipment_id
    )
else:
    query = query.filter(
        Reservation.equipment_id.is_(None)
    )
```

- 选了设备：只检查同一设备 ID。
- 没选设备：只检查 `equipment_id IS NULL` 的实验室预约。
- `.is_(None)` 生成 SQL 的 `IS NULL`，表示这一条记录没有预约设备。
- `filter()` 返回新的查询对象，必须用 `query =` 接回来，否则这次追加的条件没有被后面的查询使用。

### 6.2 两个不等式怎样判断重叠

假设已有预约是同日 10:00—11:00：

| 本次时间 | 是否冲突 | 原因 |
|---|---|---|
| 09:00—10:00 | 否 | 本次恰好在已有预约开始时结束 |
| 09:30—10:30 | 是 | 前半段重叠 |
| 10:00—10:30 | 是 | 被已有预约包含 |
| 09:00—12:00 | 是 | 包含已有预约 |
| 10:30—11:30 | 是 | 后半段重叠 |
| 11:00—12:00 | 否 | 本次恰好在已有预约结束时开始 |

使用严格的 `<`、`>`，允许两个预约在边界衔接。可以把时段理解为左闭右开的区间 `[开始, 结束)`，结束那个时刻留给下一场使用。

### 6.3 query.first() 最后才执行查询

```python
if query.first():
    raise BusinessException(message="该时段已预约")
```

`first()` 执行前面构建好的查询：

- 找到记录，返回第一条 `Reservation` 对象，说明至少存在一个冲突，抛出业务异常。
- 没找到，返回 `None`，继续创建预约。

它不是“实验室 ID 重复就报错”。同一个实验室可以在不同日期、不重叠时段有多条预约；需要全部条件同时成立才拒绝。这里只关心是否存在冲突，一条就足够，所以不必用 `.all()` 取回所有冲突记录。

### 6.4 当前资源之间的关系

| 已有记录 | 本次请求 | 相同重叠时段的结果 |
|---|---|---|
| 实验室本身 | 同一实验室本身 | 冲突 |
| 设备 A | 同一设备 A | 冲突 |
| 设备 A | 同实验室的设备 B | 互不冲突 |
| 实验室本身 | 实验室内设备 A | 分别查重，当前允许 |

因此“预约实验室”目前不等于“锁定其中所有设备”。设备的 `quantity` 也还没有变成可分配库存：当前对某个设备记录整体查重，不支持同一记录按数量同时预约多人。后续如要改规则，应明确设计后再调整。

---

## 第七章 保存预约与 API 接入

### 7.1 通过检查之后，才保存

```python
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
```

逐句理解：

1. `Reservation(...)` 创建一个 Python ORM 实例，尚未写入数据库。
2. `user_id=current_user.id` 绑定当前登录用户，不让前端指定其他人的 ID。
3. `status=0` 固定新预约为待审核，不接受前端直接提交“已通过”。
4. `db.add(reservation)` 把实例加入会话。
5. `db.commit()` 把插入操作提交到数据库。
6. `db.refresh(reservation)` 按这条记录重新读取数据库，取得主键、默认字段等最新值。

`refresh()` 需要传入对象，不能只写 `db.refresh()`。本节接口只返回提交成功，不返回预约详情，所以 service 没写 `return` 是有意的，api 也没有依赖返回值。

### 7.2 HTTP 接口负责什么

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_services
router = APIRouter(prefix="/reservation", tags=["预约相关接口"])


@router.post("")
def create_reservation(data: ReservationCreateRequest, current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    reservation_services.create_reservation(db,current_user,data)
    return Response.success()
```

`router` 的前缀是 `/reservation`，装饰器是 `@router.post("")`，再叠加总 router 的 `/api`，最终得到：

```text
POST /api/reservation
```

参数来源：

- `data`：请求体，由 `ReservationCreateRequest` 校验和解析。
- `current_user`：`Depends(get_current_user)` 解析 token，检查用户存在且未被禁用。
- `db`：`Depends(get_db)` 提供数据库会话，请求结束后关闭会话。

使用的是当前用户依赖，不是管理员依赖，所以有效登录的学生也能提交。具体资源可用性由 service 再检查。

### 7.3 导入 router 之后，还需要注册

在 `app/api/__init__.py` 中：

```python
from app.api.reservation import router as reservation_router

api.include_router(reservation_router)
```

只导入、不 `include_router()`，接口不会出现在应用中，访问会 404。

在 `app/main.py` 中导入模型：

```python
from app.models.reservation import Reservation
```

这样预约模型会参与 `Base.metadata` 的表定义。项目启动时的 `create_all()` 可以创建缺失表，但不会把已有旧字段自动改成新字段。

### 7.4 如何理解接口返回

成功：

```json
{"code":200,"message":"请求成功","data":null}
```

冲突示例：

```json
{"code":500,"message":"该时段已预约","data":null}
```

当前项目默认业务异常码是 500，业务异常处理器使用 HTTP 200 返回；这不等于每个业务错误都是服务器程序崩溃。应同时看 HTTP 状态、业务 `code` 和 `message`。缺参数一般是 HTTP 422，未登录是 HTTP 401。

---

## 第八章 前端 API：把表单连接到后端

文件：`frontend/src/api/reservation.js`。

```javascript
import request from '@/utils/request'

/**
 * 创建预约
 */
export function createReservationApi(data) {
  return request({
    url: '/api/reservation',
    method: 'post',
    data
  })
}
```

`createReservationApi` 是我们自己写的函数；内部调用项目封装的 Axios 实例。

- `url` 对应后端刚注册的路径。
- `method: 'post'` 表示创建预约。
- `data` 会作为 JSON 请求体发送，不是 URL 查询参数。
- 必须 `return request(...)`，让组件拿到 Promise，才能 `await` 并读取结果。

组件不需要再次写 Authorization。`utils/request.js` 的请求拦截器已经从本地读取 token 并附加到请求头。

注意导入路径使用普通引号：`import request from '@/utils/request'`，不能把路径写成反引号模板字符串。

---

## 第九章 为什么单独写 ReserveDialog 组件

### 9.1 views 与 components 的分工

`LabList.vue`、`LabEquipment.vue` 是通过路由进入的完整页面，放在 `views`。预约弹窗不是单独一页，是这些页面中重复使用的一部分，放在 `components`。

```text
LabList.vue       ──传实验室信息────┐
                                 ├→ ReserveDialog.vue → 同一个预约 API
LabEquipment.vue ──传实验室和设备──┘
```

父页面负责“选中哪个对象、何时打开”；子组件负责“显示表单、选择时间、校验、请求、关闭”。如果在两个页面各复制一份弹窗，以后调整时间规则就要改两份，还容易出现行为不一致。

### 9.2 props：从父页面接收预约对象

```javascript
const props = defineProps({
  visible: Boolean,
  labId: Number,
  labName: String,
  equipmentId: Number,
  equipmentName: String
})

const emit = defineEmits(['update:visible'])
const formRef = ref()
```

| 属性 | 来源和作用 |
|---|---|
| `visible` | 父页面保存的弹窗显示状态 |
| `labId`、`labName` | 所选实验室 ID，用于请求；名称用于展示 |
| `equipmentId`、`equipmentName` | 所选设备 ID 和名称；实验室预约不传 |
| `formRef` | 通过 template ref 取得 Element Plus 表单实例，调用校验/重置方法 |

`defineProps`、`defineEmits` 是 `<script setup>` 中的编译宏，不需要像 `ref` 一样手动导入。`formRef` 只是代码起的变量名，不是 Vue 内置的特殊对象。

### 9.3 visible 的双向通信

```vue
<el-dialog
      :model-value="visible"
      title="预约"
      width="450"
      :close-on-click-modal="!loading"
      :close-on-press-escape="!loading"
      :show-close="!loading"
      @update:model-value="emit('update:visible', $event)"
      @closed="handleClosed"
    >
```

父页面使用：

```vue
<ReserveDialog v-model:visible="reserveVisible" />
```

可以理解为同时传入了属性和事件监听：

```vue
<ReserveDialog
  :visible="reserveVisible"
  @update:visible="reserveVisible = $event"
/>
```

子组件通过：

```javascript
emit('update:visible', false)
```

通知父页面关闭，而不是直接修改只读的 prop。事件名必须是 `update:visible`，写成 `updatevisible` 不会自动配合 `v-model:visible`。

`el-dialog` 自己使用的是 `model-value/update:model-value`。外层组件把这个事件转发成自己的 `update:visible`，形成完整的父子通信。

请求期间，`loading=true` 会隐藏关闭按钮、禁止点击遮罩和按 Escape 关闭；取消按钮也禁用，避免请求仍在执行时把界面关闭后误以为请求取消了。

---

## 第十章 表单设计：先选一天，再选半小时时间

### 10.1 form 是前端填写状态

```javascript
const form = reactive({
  date: '',
  startTime: '',
  endTime: '',
  remark: ''
})
```

这是前端界面需要的四个值。`reactive()` 让表单字段变化可以同步到界面；`v-model="form.startTime"` 把输入与这个字段连接起来。

`form.startTime` 只是 `09:00`，本身不知道是哪一天；必须和 `form.date` 组合，才能用于提前时间判断和后端提交。

| 前端字段 | 示例 | 用途 |
|---|---|---|
| `date` | `2026-11-12` | 日期选择器 |
| `startTime` | `09:00` | 开始时间下拉 |
| `endTime` | `10:30` | 结束时间下拉 |
| `remark` | `课程实验` | 可选备注 |

### 10.2 日期和时间选择器

```vue
<el-form-item label="预约日期" prop="date">
          <el-date-picker
            v-model="form.date"
            type="date"
            placeholder="请选择预约日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            @change="revalidateTimes"
          />
        </el-form-item>

        <el-form-item label="开始时间" prop="startTime">
          <el-time-select
            v-model="form.startTime"
            start="00:00"
            step="00:30"
            end="23:30"
            :editable="false"
            placeholder="请选择开始时间（北京时间）"
            style="width: 100%"
            @change="revalidateTimes"
          />
        </el-form-item>

        <el-form-item label="结束时间" prop="endTime">
          <el-time-select
            v-model="form.endTime"
            start="00:00"
            step="00:30"
            end="23:30"
            :editable="false"
            placeholder="请选择结束时间（北京时间）"
            style="width: 100%"
          />
        </el-form-item>
```

日期选择器：

- `type="date"` 只选日期，不在一个控件里同时选择时分。
- `format` 决定显示格式，`value-format` 决定绑定到 form 的值。
- `@change="revalidateTimes"` 表示日期变了，重新检查已填写的开始、结束时间。

时间选择器：

- 用 `el-time-select` 提供固定选项，而不是提供任意分钟的输入。
- `start="00:00"`、`end="23:30"` 确定选项范围。
- `step="00:30"` 生成 00:00、00:30、01:00……23:30。
- `:editable="false"` 不允许学生在输入框里自由键入 09:17。
- `change` 绑定在真正产生选择事件的 `el-time-select` 上，不是外层 `el-form-item`。

结束时刻暂时不提供 `24:00`。选择当天 23:30 到次日 00:00 已经跨天，因此当前不能创建最后这半小时的跨日期记录；全天开放也仍受同日规则限制。

当前下拉框会列出全天的半小时刻度，并未按开放时间、冲突记录和提前时间动态禁用选项。选择后可能出现校验提示，后端也可能拒绝。这个版本完成的是规则校验，不是可用时段查询功能。

### 10.3 名称与备注

```vue
<el-form-item label="实验室">
  <span>{{ props.labName }}</span>
</el-form-item>

<el-form-item v-if="props.equipmentId" label="设备">
  <span>{{ props.equipmentName }}</span>
</el-form-item>

<el-form-item label="备注" prop="remark">
  <el-input
    v-model="form.remark"
    type="textarea"
    placeholder="请输入备注"
    maxlength="255"
    show-word-limit
  />
</el-form-item>
```

名称只展示，不能在预约弹窗里修改。设备项只在有设备 ID 时显示。所有 `el-form-item` 放在同一个 `el-form` 内，才使用统一的标签宽度和表单上下文。

备注可不填；`maxlength` 限制输入长度，`show-word-limit` 显示字数。界面上的限制不能代替后端 schema 的长度限制，后者仍列入后续完善事项。

---

## 第十一章 前端校验：rules 是怎样执行的

### 11.1 日期时间统一按北京时间计算

```javascript
// 只允许整点或半点，例如 09:00、09:30
const timePattern = /^([01]\d|2[0-3]):(00|30)$/
// 将预约日期和时间组合起来，按北京时间计算
const getTimestamp = (date, time) => {
  return new Date(`${date}T${time}:00+08:00`).getTime()
}
```

正则逐段理解：

| 部分 | 含义 |
|---|---|
| `^`、`$` | 整个输入必须完整匹配 |
| `[01]\d` | 小时 00—19 |
| `2[0-3]` | 小时 20—23 |
| `:` | 时分分隔符 |
| `(00|30)` | 分钟只能是 00 或 30 |

`getTimestamp()` 拼出 `2026-11-12T09:00:00+08:00`，再用 `getTime()` 转为毫秒时间戳。显式附加 `+08:00`，避免让浏览器按电脑的其他时区解释这些时间。

JavaScript 时间戳单位是毫秒，所以一小时是 `60 * 60 * 1000`，半小时是 `30 * 60 * 1000`。Python 后端则使用 `timedelta`，不要把两边单位混用。

### 11.2 开始时间校验

```javascript
const validateStartTime = (rule, value, callback) => {
  if (!value) {
    return callback()
  }

  if (!timePattern.test(value)) {
    return callback(new Error('开始时间只能选择整点或半点'))
  }

  // 日期未选时，交给日期的 required 规则提示
  if (!form.date) {
    return callback()
  }

  const start = getTimestamp(form.date, value)
  const now = Date.now()

  if (!Number.isFinite(start)) {
    return callback(new Error('请选择有效的预约日期和时间'))
  }

  if (start < now + 60 * 60 * 1000) {
    return callback(new Error('请至少提前1小时预约'))
  }

  if (start > now + 7 * 24 * 60 * 60 * 1000) {
    return callback(new Error('最多只能提前7天预约'))
  }

  callback()
}
```

执行顺序：

1. 没选时间就暂时返回，空值由 `required` 给出“请选择开始时间”。
2. 用正则检查是不是半小时刻度。
3. 日期还没选就先不做组合判断，日期也有自己的必填规则。
4. 把日期和时分组合，检查是否得到有效时间戳。
5. 与当前时刻加 1 小时、加 7 天分别比较。
6. 没有问题，调用 `callback()` 表示通过。

这里的 `callback` 是校验框架传进来的函数。`callback(new Error('...'))` 表示不通过，并在表单项下方显示提示。前面的 `return` 保证本次检查到错误后就停止，不继续调用第二次回调。

### 11.3 结束时间校验

```javascript
const validateEndTime = (rule, value, callback) => {
  if (!value) {
    return callback()
  }

  if (!timePattern.test(value)) {
    return callback(new Error('结束时间只能选择整点或半点'))
  }

  if (!form.date || !form.startTime) {
    return callback()
  }

  const start = getTimestamp(form.date, form.startTime)
  const end = getTimestamp(form.date, value)

  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return callback(new Error('请选择有效的预约日期和时间'))
  }

  if (end <= start) {
    return callback(new Error('结束时间必须晚于开始时间'))
  }

  if (end - start < 30 * 60 * 1000) {
    return callback(new Error('单次预约至少30分钟'))
  }

  callback()
}
```

结束时间同样检查半小时格式，然后使用**同一个日期**分别计算开始和结束：

```text
start = 选中日期 + 开始时间
end   = 选中日期 + 结束时间
```

结束必须大于开始，差值必须至少半小时。因为不另外选择结束日期，所以界面不会通过“结束时分比开始小”自动推断成次日，而是直接提示顺序错误。

### 11.4 rules 把规则绑定到表单字段

```javascript
const rules = {
  date: [
    {
      required: true,
      message: '请选择预约日期',
      trigger: 'change'
    }
  ],
  startTime: [
    {
      required: true,
      message: '请选择开始时间',
      trigger: 'change'
    },
    {
      validator: validateStartTime,
      trigger: 'change'
    }
  ],
  endTime: [
    {
      required: true,
      message: '请选择结束时间',
      trigger: 'change'
    },
    {
      validator: validateEndTime,
      trigger: 'change'
    }
  ],
  remark: [
    {
      max: 255,
      message: '备注不能超过255个字符',
      trigger: 'blur'
    }
  ]
}
```

需要保持三个名字一致：

```text
form.startTime
      ↕
<el-form-item prop="startTime">
      ↕
rules.startTime
```

- `required`：检查有没有填写。
- `validator`：执行上面自己写的校验函数。
- `trigger: 'change'`：选择改变时检查。
- `trigger: 'blur'`：离开输入框时检查。

`rules` 不是自动发送请求的工具，它只是校验规则对象。真正提交前还要手动调用 `formRef.value.validate()`。

### 11.5 为什么日期/开始时间改变后要重验

```javascript
// 日期或开始时间变化时，重新检查已填写的时间
const revalidateTimes = () => {
  if (form.startTime) {
    formRef.value?.validateField('startTime').catch(() => {})
  }

  if (form.endTime) {
    formRef.value?.validateField('endTime').catch(() => {})
  }
}
```

例如原来明天 09:00—10:00 有效，把开始改为 10:30 后，结束时间也应该立即提示错误；只监听结束控件自己变化，就无法及时更新这个提示。

`validateField()` 只重新检查指定字段，不提交请求。校验不通过时 Promise 会拒绝，提示已经由表单展示，因此用 `.catch(() => {})` 消化这个预期的拒绝，避免未处理的 Promise 错误。这里不代表忽略后端请求失败。

`formRef.value?.` 使用可选链：表单实例尚未挂载时跳过调用，避免访问空对象。

---

## 第十二章 提交函数：从点击按钮到关闭弹窗

### 12.1 按钮怎样调用逻辑

```vue
<template #footer>
        <el-button :disabled="loading" @click="emit('update:visible', false)"> 取消 </el-button>

        <el-button type="primary" :loading="loading" @click="handleSubmit"> 提交预约 </el-button>
      </template>
```

“取消”只通知父组件关闭，不创建记录。“提交预约”调用 `handleSubmit`。`:loading="loading"` 控制提交按钮的等待状态，不等于把数据提交到后端，真正请求在函数中执行。

### 12.2 handleSubmit 完整代码

```javascript
const loading = ref(false)
const handleSubmit = async () => {
  if (loading.value || !formRef.value) {
    return
  }

  // 先校验表单；不通过时，表单会显示具体错误
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 防止组件没有收到预约对象
  if (!props.labId) {
    ElMessage.error('缺少实验室信息，请重新选择')
    return
  }

  // 防止校验等待期间重复提交
  if (loading.value) {
    return
  }

  loading.value = true

  try {
    const res = await createReservationApi({
      lab_id: props.labId,
      equipment_id: props.equipmentId ?? null,
      start_at: `${form.date}T${form.startTime}:00`,
      end_at: `${form.date}T${form.endTime}:00`,
      remark: form.remark
    })

    if (res.code === 200) {
      ElMessage.success('预约提交成功，请等待审核')
      emit('update:visible', false)
    }
  } catch (error) {
    // 请求错误提示已经由 request.js 的拦截器处理
    console.error('提交预约失败', error)
  } finally {
    loading.value = false
  }
}
```

按执行过程拆开理解：

**第一步：拦截重复请求和未就绪的表单。**

```javascript
if (loading.value || !formRef.value) {
  return
}
```

请求已经在运行就不再发一次；表单实例还没挂载也先不处理。

**第二步：等待表单校验。**

```javascript
try {
  await formRef.value.validate()
} catch {
  return
}
```

`await` 等校验完成。校验失败时表单会显示错误，进入 `catch` 后直接结束，不设置加载状态、不发送请求。这一步还会重新判断提前时间，避免用户很久以前选中的时段在提交时已经太近。

**第三步：检查父页面是否传入实验室 ID。**

```javascript
if (!props.labId) {
  ElMessage.error('缺少实验室信息，请重新选择')
  return
}
```

没有预约对象时不发请求。后端仍会独立检查这个 ID 对应的记录是否存在。

**第四步：再次检查 loading，然后开始请求。**

校验本身是异步操作，两个快速点击可能都在等待校验；第二次 `loading` 判断可阻止后完成校验的那次继续重复发请求。它只保护当前弹窗，并不能解决多浏览器并发抢同一个时段的问题。

**第五步：把前端表单转成后端请求。**

```javascript
start_at: `${form.date}T${form.startTime}:00`,
end_at: `${form.date}T${form.endTime}:00`
```

例如日期 11 月 12 日、时间 09:00—10:30，转成完整的 `2026-11-12T09:00:00` 和 `2026-11-12T10:30:00`。末尾的 `:00` 表示秒为零。

`props.equipmentId ?? null` 表示没有设备 ID 时提交 `null`。名称无需发送，后端根据 ID 查真实记录；预约人和审核状态也不从表单发送。

**第六步：仅在业务码 200 时提示成功并关闭。**

当前 Axios 响应拦截器可能已经显示业务错误，但对于部分业务错误仍会返回响应对象，因此不能把“await 正常返回”直接等同于预约成功。

```javascript
if (res.code === 200) {
  ElMessage.success('预约提交成功，请等待审核')
  emit('update:visible', false)
}
```

业务冲突时不关闭，方便用户调整时段。成功提示强调等待审核，与数据库中的 `status=0` 保持一致。

**第七步：finally 恢复加载状态。**

```javascript
finally {
  loading.value = false
}
```

成功、业务失败、网络异常都要恢复按钮和关闭入口，不能把这句只放在成功分支里。请求级异常提示主要由 `request.js` 拦截器处理，当前组件的 `catch` 记录到控制台，不再重复弹同一错误。

### 12.3 关闭后为什么重置表单

```javascript
const handleClosed = () => {
  formRef.value?.resetFields()
}
```

`@closed` 在弹窗关闭动画结束后调用 `handleClosed()`。`resetFields()` 会把有 `prop` 的字段恢复为初始值，并清理校验提示。

这样第一次预约 A 实验室后关闭，再预约 B 实验室时，不会把 A 的日期、时间、备注带过去。`resetFields()` 只影响前端界面，不会删除数据库里已经提交的预约。

---

## 第十三章 两个父页面如何共用组件

### 13.1 实验室列表：只传实验室

文件：`frontend/src/views/LabList.vue`。

```javascript
import ReserveDialog from '@/components/ReserveDialog.vue'

const reserveVisible = ref(false)
const selectedLab = ref({})

const goReserve = (lab) => {
  selectedLab.value = lab
  reserveVisible.value = true
}
```

列表中原有按钮继续调用：

```vue
<el-button
  size="small"
  type="primary"
  :disabled="lab.status !== 1"
  @click="goReserve(lab)"
>
  预约
</el-button>
```

页面模板放一个共用实例：

```vue
<ReserveDialog
  v-model:visible="reserveVisible"
  :lab-id="selectedLab.id"
  :lab-name="selectedLab.name"
/>
```

执行顺序是“保存 lab → 打开弹窗”。在脚本中 ref 使用 `.value`，模板会自动解包，所以模板写 `selectedLab.id`。

这个组件实例放在卡片 `v-for` 外面，一页只创建一个预约弹窗，不需要每个实验室卡片都创建一份。没有传 `equipment-id`，提交时自动使用 `null`。

当前源码把 `ReserveDialog` 与页面主 `div` 并列放在 template 下。Vue 3 支持多个根节点，因此这里不属于语法错误；它仍然在卡片循环外。

### 13.2 设备列表：传实验室和设备

文件：`frontend/src/views/LabEquipment.vue`。

```javascript
import ReserveDialog from '@/components/ReserveDialog.vue'

const reserveVisible = ref(false)
const selectedEquipment = ref({})

const goReserve = (equipment) => {
  selectedEquipment.value = equipment
  reserveVisible.value = true
}
```

```vue
<ReserveDialog
  v-model:visible="reserveVisible"
  :lab-id="selectedEquipment.lab_id"
  :lab-name="selectedEquipment.lab_name"
  :equipment-id="selectedEquipment.id"
  :equipment-name="selectedEquipment.name"
/>
```

设备行对象由第 16 节接口返回，已经包含 `lab_id`、`lab_name`。父页面直接把这些信息传入，弹窗仍然调用同一个创建接口。

设备按钮已经限制状态正常、数量大于零才可点击。但本节后端只检查设备存在、归属和状态，尚未对数量为零增加独立校验，也没有实现按数量分配预约，二者不能混为一谈。

### 13.3 props 为什么大小写不一样

JavaScript 中声明 `labId`，模板传参写 `:lab-id`，是 Vue 常见的命名对应方式。

| 子组件声明 | 父模板绑定 | 发给后端 |
|---|---|---|
| `labId` | `:lab-id` | `lab_id` |
| `equipmentId` | `:equipment-id` | `equipment_id` |
| `labName` | `:lab-name` | 不发送，只展示 |

前端内部名称、模板属性和后端 JSON 字段可以不同，但转换的位置必须清楚。

---

## 第十四章 数据库迁移与运行版本

### 14.1 这次为什么必须迁移

旧表是 `date/start_time/end_time`，新 model 使用 `start_at/end_at`。`Base.metadata.create_all()` 不会自动修改已有表。

因此存在两个不同问题：

1. 磁盘 schema 已改、运行中的服务未重启：OpenAPI 仍显示旧字段，提交新格式可能 422。
2. 服务已加载新 model、数据库未迁移：查询会提示新列不存在；如果旧必填列保留，插入也可能失败。

代码、表结构、运行中的进程都需要同步，单独改其中一个不能完成更新。

### 14.2 保留旧数据的迁移步骤

以下是给**仍处于旧表结构**的环境参考的手动方案。先停止使用旧接口的进程、备份表，再执行。当前学习环境已经完成迁移，不要重复运行这些语句。

先新增可空列：

```sql
ALTER TABLE reservations
    ADD COLUMN start_at DATETIME NULL COMMENT '预约开始日期时间',
    ADD COLUMN end_at DATETIME NULL COMMENT '预约结束日期时间';
```

将旧的同日预约转换：

```sql
UPDATE reservations
SET
    start_at = STR_TO_DATE(
        CONCAT(`date`, ' ', start_time),
        '%Y-%m-%d %H:%i'
    ),
    end_at = STR_TO_DATE(
        CONCAT(`date`, ' ', end_time),
        '%Y-%m-%d %H:%i'
    );
```

先核对再继续：

```sql
SELECT id, `date`, start_time, end_time, start_at, end_at
FROM reservations;

SELECT COUNT(*) AS invalid_rows
FROM reservations
WHERE start_at IS NULL OR end_at IS NULL OR end_at <= start_at;
```

有异常数据时先确认含义，不能直接把结束时间较小的记录推断为次日。确认转换无误后，设为非空并移除旧列：

```sql
ALTER TABLE reservations
    MODIFY COLUMN start_at DATETIME NOT NULL
        COMMENT '预约开始日期时间',
    MODIFY COLUMN end_at DATETIME NOT NULL
        COMMENT '预约结束日期时间',
    DROP COLUMN `date`,
    DROP COLUMN start_time,
    DROP COLUMN end_time;
```

MySQL 结构变更涉及隐式提交，不能把“后面出错就简单 rollback”当作完整回滚方案，先备份再变更。

本学习环境在 2026-11-10 已完成实际迁移：迁移前后都是 0 条预约，保留了数据库备份表和仓库外的本地备份；其他字段未变。实际迁移过程做了锁定、备份和前后核对，以上 SQL 是便于理解的分步说明。

数据库内容、备份、真实连接配置不上传 GitHub。源码上传并不会同步别人的 MySQL 表结构，旧环境仍需自行迁移。

### 14.3 重启与检查

迁移并保存代码后，重启后端，查看：

```text
GET /openapi.json
components.schemas.ReservationCreateRequest.properties
```

字段应包含 `lab_id/equipment_id/start_at/end_at/remark`。但 OpenAPI 只反映接口结构，不能证明 service 的最新业务规则已经加载；本次后续增加同日、半小时规则时，schema 没变，所以还需要用跨天和非半小时请求做实际验证。

---

## 第十五章 验证：区分最终版本和历史结果

### 15.1 最终源码的实际回归结果

2026-11-10 按最终“同日、半小时”源码进行验证：

| 验证方式 | 结果 |
|---|---|
| 实际 curl 调用创建预约接口 | 35 项通过 |
| 数据库核对保存用户及同日记录 | 1 项通过 |
| 本次测试数据清理核对 | 1 项通过 |
| 合计 | 37 / 37 通过 |
| 前端生产构建 | 通过 |
| 单独的 service 时间规则检查 | 8 项通过，不连接数据库 |

由于用户原有 8000 端口服务仍加载旧规则，本次用临时 18018 端口启动当前源码的 router 与统一异常处理器，连接同一学习数据库进行 curl 回归，没有替用户重启或打断 8000 服务。临时服务已停止。

测试创建并清理了 8 条预约、2 台设备、3 个实验室；只使用本次唯一标记的数据，没有修改已有业务记录。自动验证使用管理员登录调用当前用户接口，**没有单独完成学生浏览器的端到端点击验证**。

最终 curl 覆盖：

| 分类 | 检查情况 |
|---|---|
| 身份与格式 | 未登录、缺少必填字段、无效日期格式 |
| 同日 | 跨天请求拒绝 |
| 时间先后 | 结束相同、结束早于开始均拒绝 |
| 半小时刻度 | 非整点/半点开始与结束、非零秒、微秒均拒绝 |
| 时长 | 15 分钟无效，30 分钟与 90 分钟有效 |
| 提前时间 | 过去、不足 1 小时、超过 7 天均拒绝 |
| 实验室 | 不存在、关闭、早于开放、晚于关闭 |
| 设备 | 不存在、实验室归属错误、维修状态 |
| 冲突 | 完全相同、部分重叠、包含旧时段，同设备重叠 |
| 不冲突 | 边界衔接、不同实验室、不同日期 |
| 状态 | 待审核和已通过占用；已拒绝、已取消不占用 |
| 时区 | UTC 表示的等价时间能识别冲突 |

15 分钟请求首先命中刻度校验，所以其预期错误是“只能选择整点或半点”。八项单独 service 检查还覆盖零时长、倒序、跨天及有效 30/90 分钟。

### 15.2 为什么不能把早先的 51 项结果直接算作最终验证

本节中途尝试过跨天预约，早先版本的 51 项检查包含“跨天成功”。后来明确收敛为同日预约，这项预期已经改变，不能把旧结果作为最终行为说明。

原 8000 服务的最终规则预检曾出现 7 项不符合新预期；原因是旧服务还允许非半小时或跨天逻辑，部分旧规则请求还产生了新的时段占用，继而影响后续检查。该批次测试数据同样已清理。当前源码在独立进程中重新验证后，37 项全部通过。

当前用户服务若未重启，仍需要重启才会应用最终规则。不能用“文件保存了”或“前端构建成功了”代替“运行中的后端已经加载新逻辑”。

### 15.3 自己怎样用 curl 验证

先设置地址并用自己的测试账号登录，示例全部使用占位凭据：

```bash
export BASE_URL='http://localhost:8000'

curl -sS -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'

export TOKEN='YOUR_ACCESS_TOKEN'
```

使用自己创建的测试实验室，配置满足要求的开放时间。下面的日期、ID 都需要按实际数据替换：

```bash
export LAB_ID='YOUR_LAB_ID'
export RESERVE_DATE='YYYY-MM-DD'

curl -sS -i -X POST "$BASE_URL/api/reservation" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"lab_id\":$LAB_ID,
    \"start_at\":\"${RESERVE_DATE}T09:00:00\",
    \"end_at\":\"${RESERVE_DATE}T10:30:00\",
    \"remark\":\"手动预约测试\"
  }"
```

日期时间必须处于当前允许预约的区间，不能照抄过期的固定日期。成功会真实写入待审核记录；重复执行同一请求应提示冲突。本节还没有取消接口，手动验证请使用独立测试数据，清理由明确的数据管理步骤完成。

设备预约在同一请求中增加 `equipment_id` 即可，其值必须属于该实验室。

### 15.4 浏览器自测步骤（待用户实际确认）

1. 学生登录进入实验室列表，点开放实验室的预约按钮，核对名称。
2. 日期单独选择；开始、结束下拉只出现 00/30 分钟，不能输入任意分钟。
3. 不填日期或时间提交，应出现对应表单项的必填提示。
4. 选未来的有效 30 分钟或 90 分钟，提交后提示等待审核并关闭。
5. 重新打开另一实验室，确认时间、备注、旧错误提示已清空。
6. 进入设备列表预约，核对实验室和设备名称、Network 中的两个 ID。
7. 重复提交已占用时段，弹出冲突提示，弹窗保持打开，加载状态恢复。
8. 修改日期、开始时间，观察结束时间错误提示是否及时更新。

以上是建议执行的浏览器清单，不把未实际执行的项目标为已通过。

---

## 第十六章 本课排错记录

| 现象或代码 | 原因 | 本课处理方式 |
|---|---|---|
| `from aap.models...` | 包名拼写错误 | 改为 `app` |
| 预约接口 404 | 导入 router 后未注册 | 补 `api.include_router(reservation_router)` |
| 新请求 422 | schema 字段仍是旧名，或运行服务未更新 | 对齐新字段并重启 |
| 新列不存在 | model 更新，旧表未迁移 | 备份、迁移，再重启 |
| `query.filter(...)` 后条件无效 | 没接收新 query | 使用 `query = query.filter(...)` |
| 只预约实验室时报 equipment 未定义 | 设备检查缩进在条件外 | 把全部设备检查放入设备分支 |
| A 实验室能提交 B 实验室设备 | 只查设备存在，漏归属 | 比较 `equipment.lab_id` |
| 提交入库但随后报错 | `commit()` 后调用无参数 `refresh()` | 使用 `db.refresh(reservation)` |
| 当前时分比较混乱 | `%H-%M` 与 `HH:mm` 不一致，且用结束判断过期 | 改为完整 datetime 和 timedelta |
| 前端等待不到 API 结果 | API 函数没 return | `return request(...)` |
| import 语法错误 | 静态路径使用反引号 | 使用普通字符串引号 |
| 弹窗关闭父状态未变 | 事件名 `updatevisible` 不匹配 | 使用 `update:visible` |
| 时间变化不重验 | `change` 写在外层 form-item | 绑到选择器上 |
| 名称与表单错位 | form-item 在 form 外 | 移进统一的 el-form |
| 设备按钮仍提示开发中 | goReserve 还是占位函数 | 保存设备对象并打开弹窗 |
| 文件顶部写 `#说明` | 误用了 Python/Markdown 注释 | Vue 中使用 `<!-- 说明 -->` |

---

## 第十七章 自检：能不能用自己的话解释

- [ ] 为什么前端 form 有 date/startTime/endTime，后端却只有 start_at/end_at？
- [ ] `datetime` 和只保存日期的 `date` 有什么区别？
- [ ] 为什么规定北京时间，带时区的输入要先转换再去掉标记？
- [ ] 为什么用开始时间判断至少提前 1 小时，而不是用结束时间？
- [ ] 整点/半点、秒为 0、正时长为什么能保证半小时倍数？
- [ ] `query` 是结果还是查询对象？`first()` 在哪一步执行？
- [ ] 多次 `filter()` 之间是什么关系？为什么要接收返回值？
- [ ] 同一个实验室 ID 的两条预约，为什么不一定冲突？
- [ ] 两个时间重叠条件为什么可以允许首尾衔接？
- [ ] `equipment_id=None` 与传设备 ID 分别筛选什么记录？
- [ ] 为什么创建时的 user_id 和 status 不直接使用前端提交值？
- [ ] `props`、`emit`、`v-model:visible` 如何连起来？
- [ ] 为什么组件只在父页面放一次，而不是放进卡片循环？
- [ ] `callback(new Error(...))` 和 `.catch(() => {})` 各在处理什么？
- [ ] `commit()`、`refresh()`、`resetFields()` 分别影响什么？
- [ ] 提交成功为什么不等于审核通过？
- [ ] 保存代码、迁移表结构、重启服务为什么是三件不同的事？

---

## 下一课：开发我的预约和预约审核

第 19 节继续围绕已有 `Reservation` 记录开发：

- 学生查看自己的预约及审核状态。
- 管理员查看待处理预约并进行审核。
- 关联展示实验室、设备、预约人和完整时间。
- 列表查询范围与操作权限由后端控制，不能仅靠前端隐藏按钮。

具体接口路径、筛选字段和状态更新规则以下一课实际代码为准。本节不提前把尚未开发的列表、审核或取消接口写成已有能力。

---

## 附录：课程结束后统一完善

本节先保留课堂实现，以下事项记录后集中完善，不在写笔记时擅自修改业务代码。

| 事项 | 当前行为与后续方向 |
|---|---|
| 并发预约 | 先查再插入，两个并发请求仍可能同时查不到；以后结合事务和按资源加锁设计，不是加一条开始时间唯一约束就能解决区间重叠 |
| 实验室与设备联动 | 当前分别查重；是否包场锁定所有设备，需要明确业务规则 |
| 设备数量 | 前端数量为 0 禁用，后端未独立检查数量，也未实现按数量预约 |
| 后端字段约束 | `remark` 尚未在 schema 设置 255 字符上限，部分 ID 合法范围也可补充 |
| 可空类型声明 | 模型 remark、equipment 关联的类型注解可与实际可空性统一 |
| 可用时段体验 | 当前全天刻度都显示；可进一步根据开放时间、提前时间及冲突禁用不可选项，后端仍须校验 |
| 日期可选范围 | 当前日期控件未直接禁用过去日期，选择开始时间/提交时才检查完整时刻 |
| 开放配置一致性 | 管理端目前主要限制同日白天开放，service 保留夜间/全天解释；后续统一管理入口与展示文案 |
| 时区体验 | 当前按北京时间解释表单，浏览器本机日期的“今天”提示等仍可在异地时区环境优化 |
| 状态与错误链 | 统一业务错误码、Axios 拒绝策略、数据库异常回滚处理可进一步规范 |
| 取消与审核 | 待下一课明确状态流转、本人权限、管理员权限及重复操作规则 |
| 已有边界 | 学生菜单隐藏不等于安全限制；后端校验和读取范围仍是权限依据 |
| 清理项 | 父页面保留的未用 ElMessage 导入、设备页面“预约占位”旧注释可统一清理，不影响当前主流程 |
| 其他历史问题 | 原有实验室详情接口的路径参数绑定、状态值 0 的筛选、重复设备路由等不在本课改动范围，另行集中检查 |

本节最终知识主线：**前端让学生清楚地选一天和半小时时段，后端用完整日期时间严格判断可预约性，成功后只创建待审核记录。**
