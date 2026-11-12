# 开发我的预约与预约审核

> 对应课程：第 19 节
> 对应项目：`agent-lab/lab-system-agent`
> 前置课程：第 18 节实验室预约
> 最终版本：实验室必选、设备可选（0/2），实验室时段独占；我的预约列表、学生取消、管理员审核（通过/拒绝）
> 整理日期：2026-11-12
> 阅读方式：按“代码做什么 → 每一步为什么这样写 → 前端参数如何对应后端”理解。

---

## 第零章 这节课完成了什么

第 18 节只完成了“创建一条待审核预约”，没有列表、取消和审核。本节补齐这条完整链路：

```text
学生创建预约(status=0)
    ↓
我的预约列表查看（学生只看自己，管理员看全部）
    ↓
学生取消(status=0 → 3) 或 管理员审核(status=0 → 1 通过 / 2 拒绝)
    ↓
冲突检查只看 status in (0,1)，所以取消/拒绝后时段自动释放
```

同时，本节明确了预约的三种业务模式：

| `reservation_type` | 含义 | 占用实验室 | 占用设备 |
|---|---|---|---|
| 0 | 仅实验室 | ✅ | ❌ |
| 1 | 仅设备 | ❌ | ✅ |
| 2 | 实验室+设备 | ✅ | ✅ |

最终前端只产生 **0** 和 **2** 两种类型：预约实验室是必选，设备可选。

- 不选设备 → 仅实验室(0)
- 选了设备 → 实验室+设备(2)

原因：设备一般带不走，使用设备必然人在实验室内，所以“仅设备”在当前业务下没有独立入口。类型 1 仍保留在后端，用于兼容历史数据和后续升级，前端不再创建新的 type=1 记录。

> 业务约定：**实验室按时段独占**。只要某时段被仅实验室(0)或实验室+设备(2)占用，其他人同一时段就不能再预约该实验室（包括其中的设备）。

### 0.1 本节涉及哪些文件

| 文件 | 本节承担的作用 |
|---|---|
| `backend/app/models/reservation.py` | 新增 `reservation_type` 字段 |
| `backend/app/schemas/reservation.py` | 创建请求带类型、审核请求体 |
| `backend/app/services/reservation_services.py` | 类型校验、冲突规则、取消、审核 |
| `backend/app/api/reservation.py` | 新增取消接口、审核接口 |
| `frontend/src/api/reservation.js` | 列表、取消、审核的请求封装 |
| `frontend/src/views/MyReservation.vue` | 学生端我的预约页面 |
| `frontend/src/views/ReservationAudit.vue` | 管理员预约审核页面 |
| `frontend/src/utils/reservation.js` | 状态/类型/时间的公共映射函数 |
| `frontend/src/components/ReserveDialog.vue` | 实验室必选、设备可选，自动推导 `reservation_type` |
| `frontend/src/layouts/Layout.vue` | 学生“我的预约”、管理员“预约审核”菜单 |
| `frontend/src/router/index.js` | 注册我的预约与预约审核路由 |

### 0.2 状态流转表

| 当前状态 | 操作 | 结果 |
|---|---|---|
| 0 待审核 | 管理员通过 | 1 已通过（继续占用时段） |
| 0 待审核 | 管理员拒绝 | 2 已拒绝（释放时段） |
| 0 待审核 | 学生取消 | 3 已取消（释放时段） |
| 1/2/3 | 再次审核/取消 | 拒绝，提示当前状态不可操作 |

---

## 第一章 三种预约类型

### 1.1 为什么必须加字段

仅凭 `equipment_id` 是否为空，只能区分“有没有设备”，无法区分“仅设备”和“实验室+设备”——这两者在库里都是 `equipment_id` 非空。没有类型字段，冲突检查就无法按业务规则区分占用对象。

所以模型新增：

```python
reservation_type: Mapped[int] = mapped_column(
    comment="预约类型 0仅实验室 1仅设备 2实验室+设备", default=0
)
```

**迁移提示**：`Base.metadata.create_all` 只建缺失的表，不会给已有表加列，必须手动执行：

```sql
ALTER TABLE reservations
  ADD COLUMN reservation_type INT NOT NULL DEFAULT 0
  COMMENT '预约类型 0仅实验室 1仅设备 2实验室+设备';

UPDATE reservations SET reservation_type = 2 WHERE equipment_id IS NOT NULL;
UPDATE reservations SET reservation_type = 0 WHERE equipment_id IS NULL;
```

### 1.2 类型与设备字段的组合校验

放在 service 里而不是 schema 的 `model_validator`，因为项目的参数异常处理器（`app/common/exceptions.py`）会把所有参数错误统一成“请求参数校验错误”，前端拿不到具体原因；用 `BusinessException` 才能返回明确提示。

```python
if data.reservation_type not in (0, 1, 2):
    raise BusinessException(message="无效的预约类型")
if data.reservation_type == 0 and data.equipment_id is not None:
    raise BusinessException(message="仅预约实验室时不能选择设备")
if data.reservation_type in (1, 2) and data.equipment_id is None:
    raise BusinessException(message="该预约类型必须选择设备")
```

### 1.3 冲突检查按“占用对象”拆成两段

```python
# 占用实验室的类型：0、2
if data.reservation_type in (0, 2):
    exists = db.query(Reservation).filter(
        Reservation.lab_id == data.lab_id,
        Reservation.reservation_type.in_([0, 2]),
        Reservation.status.in_([0, 1]),
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    ).first()
    if exists:
        raise BusinessException(message="该时段实验室已被预约")

# 占用设备的类型：1、2
if data.reservation_type in (1, 2):
    exists = db.query(Reservation).filter(
        Reservation.equipment_id == data.equipment_id,
        Reservation.reservation_type.in_([1, 2]),
        Reservation.status.in_([0, 1]),
        Reservation.start_at < end_at,
        Reservation.end_at > start_at,
    ).first()
    if exists:
        raise BusinessException(message="该设备在该时段已被预约")
```

两个 `if` 是独立的，不是 `elif`：type=2 必须两边都查。

注意一个 Python 细节：类型判断必须用 `in`，不能写 `is`：

```python
if data.reservation_type is (1, 2):   # ❌ 恒为 False
if data.reservation_type in (1, 2):   # ✅
```

`is` 比较对象身份，`int` 和 `tuple` 永远不是同一个对象，写错会导致设备校验整段被跳过。

---

## 第二章 我的预约列表

### 2.1 后端查询规则

```python
query = db.query(Reservation)
if current_user.role != "admin":
    query = query.filter(Reservation.user_id == current_user.id)
if status is not None:
    query = query.filter(Reservation.status == status)
```

- 学生：强制过滤 `user_id = 当前用户`，看不到别人的预约
- 管理员：不加用户过滤，能看到全部预约（审核页面复用同一接口）
- 支持按状态筛选、分页、按 id 倒序
- 使用 `joinedload` 预加载 `user / lab / equipment`，再补名称字段，避免 N+1 查询

响应中每条记录包含：

```json
{
  "id": 42,
  "user_id": 7,
  "user_name": "张三",
  "lab_id": 3,
  "lab_name": "数学实验室",
  "equipment_id": null,
  "equipment_name": null,
  "start_at": "2026-11-13T09:00:00",
  "end_at": "2026-11-13T10:00:00",
  "remark": "备注",
  "status": 0,
  "reservation_type": 0
}
```

---

## 第三章 学生取消预约

### 3.1 规则

- 只能取消**自己的**预约
- 只有 `status == 0`（待审核）可以取消
- 已取消(3) 重复取消给出明确提示
- 已通过(1)/已拒绝(2) 不允许取消
- 取消后 `status=3`，由于冲突检查只看 0/1，时段自动释放

### 3.2 service

```python
def cancel_reservation(db: Session, current_user: User, reservation_id: int):
    item = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,
            Reservation.user_id == current_user.id,
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
```

**为什么查询时就带 `user_id`**：别人的预约根本查不出来，统一返回“不存在或无权操作”，既不泄露数据存在性，也少一层判断。

### 3.3 API

```python
@router.put("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation_services.cancel_reservation(db, current_user, reservation_id)
    return Response.success(message="预约已取消")
```

---

## 第四章 管理员预约审核

### 4.1 权限

管理员校验使用现成依赖 `get_current_admin`（`app/dependencies/auth.py`），非管理员直接返回：

```json
{ "code": 403, "message": "无权限访问", "data": null }
```

不要在 service 里重复写角色判断，权限只放在 API 层，service 只负责业务规则。

### 4.2 审核请求体

```python
class ReservationAuditRequest(BaseModel):
    status: int  # 1-通过 2-拒绝
```

### 4.3 service

```python
def audit_reservation(db: Session, current_user: User, reservation_id: int, status: int):
    item = db.query(Reservation).filter(Reservation.id == reservation_id).first()

    if not item:
        raise BusinessException(message="预约记录不存在")

    if status not in (1, 2):
        raise BusinessException(message="无效的审核结果")

    if item.status != 0:
        raise BusinessException(message="只有待审核的预约可以审核")

    item.status = status
    db.commit()
```

**为什么不能“存在就通过”**：如果不检查当前状态，已取消或已拒绝的记录会被重新通过，导致时段被错误占用。审核必须从“待审核(0)”出发。

### 4.4 API

```python
@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,
    data: ReservationAuditRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    reservation_services.audit_reservation(db, current_user, reservation_id, data.status)
    return Response.success(message="审核完成")
```

---

## 第五章 前端实现

### 5.1 `api/reservation.js`

```js
export function createReservationApi(data) {
  return request({ url: '/api/reservation', method: 'post', data })
}

export function getReservationListApi(params) {
  return request({ url: '/api/reservation/list', method: 'get', params })
}

export function cancelReservationApi(reservationId) {
  return request({ url: `/api/reservation/${reservationId}/cancel`, method: 'put' })
}

export function auditReservationApi(reservationId, status) {
  return request({
    url: `/api/reservation/${reservationId}/audit`,
    method: 'put',
    data: { status }
  })
}
```

> 注意：原来文件里两个函数都叫 `createReservationApi`，后者会覆盖前者，导致提交预约实际请求到了列表接口。函数命名必须唯一。

### 5.2 `ReserveDialog.vue`：实验室必选、设备可选

最终交互不再让学生手选 0/1/2，而是只做两个决定：

1. 预约哪个实验室（进入弹窗时已确定，只展示）
2. 要不要同时预约设备（下拉选择，可以不选）

弹窗里增加设备下拉：

```vue
<el-form-item label="设备" prop="equipmentId">
  <el-select
    v-model="form.equipmentId"
    placeholder="不预约设备（仅使用实验室）"
    clearable
    :loading="equipmentLoading"
    style="width: 100%"
  >
    <el-option
      v-for="item in equipmentOptions"
      :key="item.id"
      :label="item.status === 1 ? item.name : `${item.name}（维修中）`"
      :value="item.id"
      :disabled="item.status !== 1"
    />
  </el-select>
  <div style="color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px">
    不选设备表示仅预约实验室；选择设备会同时占用实验室和该设备
  </div>
</el-form-item>
```

打开弹窗时按实验室加载设备，并把从 LabEquipment 页面带来的设备预选上：

```js
const loadEquipmentOptions = async () => {
  if (!props.labId) return
  equipmentLoading.value = true
  try {
    const res = await getEquipmentPageList({
      lab_id: props.labId,
      page: 1,
      page_size: 100
    })
    if (res.code === 200) {
      const list = res.data.list
      if (props.equipmentId && !list.some((item) => item.id === props.equipmentId)) {
        list.unshift({
          id: props.equipmentId,
          name: props.equipmentName || '已选设备',
          status: 1
        })
      }
      equipmentOptions.value = list
    }
  } finally {
    equipmentLoading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      form.equipmentId = props.equipmentId ?? null
      loadEquipmentOptions()
    }
  }
)
```

提交时类型由“有没有选设备”自动推导：

```js
const res = await createReservationApi({
  lab_id: props.labId,
  equipment_id: form.equipmentId || null,
  reservation_type: form.equipmentId ? 2 : 0,
  start_at: `${form.date}T${form.startTime}:00`,
  end_at: `${form.date}T${form.endTime}:00`,
  remark: form.remark
})
```

行为说明：

- 从实验室列表进入：默认不选设备 → 仅实验室(0)
- 从设备列表进入：当前设备自动预选 → 实验室+设备(2)；学生也可以清空变成仅实验室
- 维修中（`status !== 1`）的设备在下拉里禁用
- 后端不需要改动，冲突检查会自动按 type 0/2 同时判断实验室和设备

### 5.3 `MyReservation.vue`

- 状态筛选 + 刷新
- 表格列：实验室、预约类型、设备、预约日期+时间段、备注、状态、操作
- `statusType / statusText / typeText / typeTagType / formatDate / formatTimeRange` 统一放在 `src/utils/reservation.js`，学生端和审核端共用
- 仅 `status === 0` 显示“取消预约”，二次确认后调用 `cancelReservationApi`
- 后端分页，前端把 `page/page_size/status` 作为 **query 参数** 传给 `getReservationListApi`
- 状态筛选清空时值为 `''`，不能直接传给后端（会 422），要显式判断后再放进 `params`

### 5.4 `Layout.vue` 菜单

学生角色新增：

```vue
<el-menu-item index="/manager/myreservation" v-if="userInfo?.role === 'student'">
  <el-icon><Calendar /></el-icon>
  <span>我的预约</span>
</el-menu-item>
```

图标在 `main.js` 中已全局注册，不需要额外 import。

### 5.5 管理员预约审核页面 `ReservationAudit.vue`

#### 5.5.1 页面定位与访问控制

- 路由：`/manager/reservationaudit`（与项目现有 `myreservation` 的命名风格一致）
- 菜单：只在 `role === 'admin'` 时显示“预约审核”
- 权限：后端 `get_current_admin` 强制校验，学生即使手动输入 URL，点审核也会收到 403；前端菜单隐藏只是体验层

#### 5.5.2 数据来源与默认筛选

复用“我的预约”同一个接口，不新增后端接口：

```js
getReservationListApi({ page, page_size, status })
```

- 管理员 token 调用时，后端不加 `user_id` 过滤，因此能看到所有学生的预约
- 默认 `status = 0`（待审核），页面打开就是待办队列
- 下拉可切换：待审核 / 已通过 / 已拒绝 / 已取消 / 全部
- 支持分页与刷新

状态参数要注意：`el-select` 清空后可能是 `''` 而不是 `undefined`，直接传给后端 `status=''` 会触发 422。因此构造参数时显式判断：

```js
const params = { page: page.value, page_size: pageSize.value }
if (status.value !== undefined && status.value !== null && status.value !== '') {
  params.status = status.value
}
```

这样才能让“状态 0”正常传出去（0 是 falsy，不能用 `if (status.value)` 判断）。

#### 5.5.3 表格列

| 列 | 取值 |
|---|---|
| 编号 | `id` |
| 预约人 | `user_name` |
| 实验室 | `lab_name` |
| 预约类型 | `reservation_type` → 仅实验室 / 仅设备 / 实验室+设备 |
| 设备 | `equipment_name`，为空显示 — |
| 预约时间 | `start_at` 日期 + 起止时间段 |
| 备注 | `remark` |
| 状态 | `status` tag |
| 操作 | 仅 `status === 0` 显示“通过 / 拒绝” |

#### 5.5.4 审核操作流程

```text
点击「通过」或「拒绝」
    ↓
ElMessageBox 二次确认（预约人、实验室、日期、时间段）
    ↓
行级状态：row.auditing = true，row.auditAction 记录点击的是 1 还是 2
    ↓
auditReservationApi(row.id, 1 或 2)
    ↓
成功：提示“已通过/已拒绝” → 重新加载列表
    ↓
失败：request.js 拦截器统一提示（如 403 无权限）
```

行级 loading 只显示在点击的那个按钮上：

```vue
:loading="row.auditing && row.auditAction === 1"  <!-- 通过 -->
:loading="row.auditing && row.auditAction === 2"  <!-- 拒绝 -->
```

#### 5.5.5 审核后的分页处理

默认筛选是“待审核”，审核完一条后该行会从当前页消失。如果当前页正好是最后一条且 `page > 1`，需要回退一页，避免停留在空页：

```js
const reloadAfterAudit = async () => {
  await loadList()
  if (tableData.value.length === 0 && page.value > 1) {
    await loadList(page.value - 1)
  }
}
```

#### 5.5.6 公共函数抽取

`statusType / statusText / typeText / typeTagType / formatDate / formatTimeRange` 原来写在 `MyReservation.vue` 里，审核页也要用。抽到 `src/utils/reservation.js` 后，两个页面共同 import：

- 状态颜色与文案只维护一份，改一处不会漏另一处
- 时间格式统一，避免学生端和审核端显示不一致

#### 5.5.7 需要同时配置的路由与菜单

```js
// router/index.js
{
  path: 'reservationaudit',
  name: 'ReservationAudit',
  component: () => import('@/views/ReservationAudit.vue')
}
```

```vue
<!-- layouts/Layout.vue，管理员菜单 -->
<el-menu-item index="/manager/reservationaudit" v-if="userInfo?.role === 'admin'">
  <el-icon><Checked /></el-icon>
  <span>预约审核</span>
</el-menu-item>
```

#### 5.5.8 本期不做的增强

- 拒绝原因：后端没有字段，需新增 `audit_remark`
- 批量审核：后端没有批量接口
- 审核前重新复核实验室/设备状态：创建时已保证，暂不重复校验

---

## 第六章 前端参数与后端参数的对应关系（重点）

这一节回答一个最容易混淆的问题：**前端要传什么、传到哪里，是谁决定的？**

### 6.1 决定参数来源的是后端写法，不是 HTTP 方法

| 后端签名写法 | FastAPI 认为参数来自 | 前端 axios 写法 |
|---|---|---|
| 路径模板里出现 `{reservation_id}` | 路径参数 path | 拼进 URL |
| `data: SomeRequest`（Pydantic 模型） | 请求体 body | `data: { ... }` |
| 普通 `status: int`（不在路径中） | 查询参数 query | `params: { ... }` |

举例，后端：

```python
@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,                 # 路径参数
    data: ReservationAuditRequest,       # 请求体
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
```

对应前端：

```js
export function auditReservationApi(reservationId, status) {
  return request({
    url: `/api/reservation/${reservationId}/audit`, // 路径
    method: 'put',
    data: { status }                                  // 请求体
  })
}
```

实际发出的请求：

```http
PUT /api/reservation/42/audit
Authorization: Bearer xxx
Content-Type: application/json

{"status": 1}
```

后端收到后：`reservation_id = 42`，`data.status = 1`。

### 6.2 创建预约的完整对应

后端 schema：

```python
class ReservationCreateRequest(BaseModel):
    lab_id: int
    equipment_id: int | None = None   # 可选
    start_at: datetime
    end_at: datetime
    remark: str | None = None         # 可选
    reservation_type: int             # 必填
```

前端提交：

```js
createReservationApi({
  lab_id: props.labId,
  equipment_id: form.equipmentId || null,
  reservation_type: form.equipmentId ? 2 : 0,
  start_at: `${form.date}T${form.startTime}:00`,
  end_at: `${form.date}T${form.endTime}:00`,
  remark: form.remark
})
```

| 后端字段 | 前端 key | 是否必填 |
|---|---|---|
| `lab_id` | `lab_id` | 必填 |
| `equipment_id` | `equipment_id` | 可选，默认 None |
| `start_at` | `start_at` | 必填 |
| `end_at` | `end_at` | 必填 |
| `remark` | `remark` | 可选，默认 None |
| `reservation_type` | `reservation_type` | 必填 |

要点：

1. “把整个对象传进去”指的是**所有必填字段都要有**，可选字段可以省略。
2. 键名必须与后端字段名完全一致（snake_case），写成 `labId`、`reservationType` 会被当成缺失 → 422。
3. 类型必须能解析：`start_at/end_at` 必须是合法时间字符串，`reservation_type` 必须是整数。
4. Pydantic 默认忽略未定义的多余字段，但**不会**把错误的名字自动对应上。

### 6.3 常见误区：是不是因为用了 PUT 才要传 status？

不是。

- 需要传 `status`，是因为后端把它放在了 `ReservationAuditRequest` 这个**请求体模型**里。
- 如果后端把 `status` 声明成普通 `int`（且不在路径模板中），同样是 PUT，但前端会用 `params: { status }`，URL 变成 `?status=1`，不需要 body。
- 如果换成 POST，只要参数仍声明成 Pydantic 模型，照样要传 body。

HTTP 方法只表达语义（PUT 表示更新资源），不决定参数位置；**参数位置由后端签名决定**。

---

## 第七章 验收清单

### 7.1 创建与三种模式

| 用例 | 预期 |
|---|---|
| 不选设备创建预约 | 成功，`reservation_type=0` |
| 选设备创建预约 | 成功，`reservation_type=2` |
| 同一时段实验室已被仅实验室(0)占用，再选设备预约 | 实验室冲突 |
| 同一设备时间重叠 | 设备冲突 |
| 实验室和设备都空闲 | 成功 |
| type0 传设备 / type1/2 不传设备 / type=9（直接调接口） | 明确报错 |
| 设备不属于该实验室 / 不存在 / 维修中 | 明确报错 |
| 维修中设备在下拉中 | 禁用，标注“维修中” |

### 7.2 取消

| 用例 | 预期 |
|---|---|
| 取消待审核预约 | 成功，status=3 |
| 重复取消 | 该预约已取消，请勿重复操作 |
| 取消他人预约 | 预约记录不存在或无权操作 |
| 取消已通过预约 | 只有待审核的预约可以取消 |

### 7.3 审核

| 用例 | 预期 |
|---|---|
| 学生调用审核 | 403 无权限访问 |
| 审核不存在记录 | 预约记录不存在 |
| status=5 | 无效的审核结果 |
| 管理员通过 | 审核完成，status=1 |
| 重复审核 | 只有待审核的预约可以审核 |
| 拒绝后同时段重新预约 | 成功（时段已释放） |
| 列表按 status 筛选 | 只返回对应状态记录 |

---

## 第八章 实现思路复盘

这一节记录“为什么这样做”，方便以后升级时回看。

### 8.1 先定状态机，再写接口

预约的生命周期只有四条边：

```text
创建 → 待审核(0)
待审核(0) → 通过(1)
待审核(0) → 拒绝(2)
待审核(0) → 取消(3)
```

所有“能不能操作”的判断都围绕当前状态：

- 冲突检查只看 `status in (0, 1)`，所以拒绝/取消天然释放时段
- 审核、取消都只能从 `status == 0` 出发，避免把已结束的记录重新激活

先把状态机写清楚，接口和页面的按钮显隐就都跟着状态走，不会散落在各处。

### 8.2 用“占用对象”决定冲突，而不是靠字段推断

仅凭 `equipment_id` 是否为空无法表达三种模式，所以新增 `reservation_type`。冲突检查按类型拆成两段：

- 占实验室的类型（0、2）→ 查实验室时段
- 占设备的类型（1、2）→ 查设备时段

这样新增模式时只需要决定它占用谁，而不用改一长串 `if equipment_id is None`。

### 8.3 前端把“类型”翻译成“选不选设备”

最终业务约定是“实验室时段独占、设备带不走”，所以前端不暴露 0/1/2：

- 不选设备 → 仅实验室(0)
- 选设备 → 实验室+设备(2)

用户只需要做一个自然决策，类型由代码推导。type 1 保留在后端兼容历史数据，不在界面产生。

### 8.4 分层职责

| 层 | 负责 | 不负责 |
|---|---|---|
| schema | 请求形状、字段类型 | 业务规则 |
| service | 业务校验、状态流转、冲突 | 权限、HTTP |
| API | 权限依赖（`get_current_admin`）、参数来源 | 业务细节 |
| 前端 api 文件 | URL、method、data/params | 页面状态 |
| 页面 | 交互、加载、提示 | 拼接 URL |
| utils | 状态/类型/时间映射 | 请求 |

### 8.5 调试过程中真实踩过的坑

1. **`is (1, 2)` 恒为 False**：`is` 比较对象身份，设备校验整段被跳过；必须用 `in`。
2. **函数重名导出**：`api/reservation.js` 两个 `createReservationApi`，后者覆盖前者，提交预约实际打到列表接口。
3. **参数来源由后端签名决定**：路径模板 → path，Pydantic 模型 → body，普通参数 → query；PUT 本身不要求 body。
4. **状态筛选空字符串**：`el-select` 清空后是 `''`，直接传后端会 422；`0` 是 falsy，不能用 `if (status)` 判断。
5. **服务未重启**：uvicorn 没有 `--reload` 时，新加的路由仍返回 404，改完必须重启。
6. **`py_compile` 只能查语法**：缺导入、缺函数是运行时错误，用 `python -c "import app.api.reservation"` 验证模块可导入。

### 8.6 验收顺序

先用 curl 按层验证，再接前端：

1. 参数形状：类型与设备组合、非法类型
2. 资源校验：实验室存在/开放、设备存在/归属/维修
3. 冲突：type 0/1/2 的各种交叉时段
4. 状态流转：审核通过/拒绝、学生取消、重复操作
5. 列表：学生只见自己、管理员见全部、状态筛选
6. 测试数据清理，临时修改的实验室/设备状态还原

---

## 第九章 待完善

- 已通过的预约暂不支持学生取消，如需支持要另行设计（可能需要管理员确认）。
- 当前实验室按时段独占；若以后允许“多人同时使用实验室（按 `lab.capacity` 计数）”，需要把布尔冲突改为容量计数。
- type 1（仅设备）当前不在界面产生；如果以后允许把设备借出实验室，再补独立入口和对应的开放时间规则。
- 可增加拒绝原因字段（如 `audit_remark`），当前审核只改状态。
- 审核通过前可再校验实验室/设备当前状态（待审核期间可能被关闭或维修）。
- 并发重复审核/取消目前结果无害；若要严格，可用 `UPDATE ... WHERE status=0` 判断影响行数。
