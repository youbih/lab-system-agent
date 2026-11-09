# 开发实验室管理功能

> 对应课程：第 15 节
> 对应项目：`agent-lab/lab-system-agent`
> 整理日期：2026-11-09
> 涉及文件：
> - 后端：`app/models/lab.py`、`app/schemas/lab.py`、`app/services/lab_services.py`、`app/api/lab.py`
> - 后端接入：`app/api/__init__.py`、`app/main.py`
> - 前端：`src/api/lab.js`、`src/views/Lab.vue`、`src/layouts/Layout.vue`
> - 上传复用：`src/api/file.js` 与 `POST /api/files/upload`
> - 课堂补充：`app/services/user_services.py` 的个人资料更新字段排除
>
> 阅读建议：先看完整片段，再按执行顺序拆开；涉及样例的代码会注明是否是节选。

---

## 第零章 这节课干了什么

在用户管理的增删改查基础上，开发实验室管理：分页、名称搜索、新增、编辑、删除、封面上传、开放时间选择，以及管理员菜单控制。

重点不是把 User 字样全部替换为 Lab 就结束，而是让数据库模型、接口字段、请求封装、页面展示与表单规则对应同一种业务。

| 模块 | 本节完成内容 |
|---|---|
| 数据库模型 | labs 表，名称、位置、容量、时间、简介、封面与状态 |
| 后端接口 | 管理员查询、新增、更新、删除实验室 |
| 业务逻辑 | 新增查重；更新检查存在、排除自身查重；删除检查存在 |
| 前端页面 | 实验室列表、搜索、分页、共用新增/编辑弹窗和删除确认 |
| 封面 | 复用文件上传接口，先取得 URL，保存时关联实验室 |
| 开放时间 | 两个 TimePicker，使用 HH:mm 字符串，结束晚于开始 |
| 权限展示 | Layout 中实验室管理菜单仅管理员可见 |
| 用户资料补充 | 排除 role/status，避免个人资料接口修改这些字段 |

整个系统仍在跟课搭建，完成本节不代表设备管理、预约或 AI/Agent 已完成。待完善事项统一放在文档最后，课程全部结束后再评估修改。

相关基础：[第 13 节用户列表](./13-user-list.md)、[第 14 节用户增删改](./14-user-crud.md)、[第 10 节上传接口](./10-file-upload-api.md)、[第 11 节个人信息](./11-profile-update.md)。

---

## 第一章 字段：从用户页面复制后，究竟要换什么

| 实验室字段 | 含义 | 页面使用 |
|---|---|---|
| id | 实验室记录 ID | 判断新增/编辑，拼接更新/删除 URL |
| name | 实验室名称 | 表格、搜索、表单、删除提示 |
| location | 位置 | 表格与表单 |
| capacity | 容量 | 数字输入框，显示人数 |
| open_time | 开放开始时间 | TimePicker 与表格 |
| close_time | 开放结束时间 | TimePicker 与表格 |
| description | 简介 | 文本域与表格 |
| img | 封面访问路径 | 上传预览与表格封面 |
| status | 1 开放、0 关闭 | 单选框与状态标签 |

用户的 username、password、email、phone、role、avatar 不属于实验室资料，需要从 Lab.vue 的表格、表单、规则、重置、回显与提交中一起移除。

例如原页面一度用 row.img 判断有图，却用 row.avatar 显示图片，这样字段并不对应；现在判断与图片 src 都使用 img。

---

## 第二章 后端模型：数据库为什么有些字段不允许为空

### 2.1 当前 Lab 模型完整代码

```python
from sqlalchemy import String,Integer
from sqlalchemy.orm import Mapped,mapped_column
from app.database import Base


class Lab(Base):
    __tablename__="labs"
    __table_args__={"comment":"实验室信息"}

    name:Mapped[str]=mapped_column(String(50),comment="名称",nullable=False)
    location:Mapped[str]=mapped_column(String(100),comment="位置")
    capacity:Mapped[int]=mapped_column(Integer,comment="容量",default=0)
    open_time:Mapped[str]=mapped_column(String(20),comment="开放开始时间")
    close_time: Mapped[str] = mapped_column(String(20), comment="开放结束时间")
    description:Mapped[str]=mapped_column(String(500),comment="简介")
    img:Mapped[str]=mapped_column(String(100),comment="封面")
    status:Mapped[int]=mapped_column(
        Integer,comment="状态:0-关闭,1-开放",default=1
    )
```

**按执行顺序拆解：**

#### 第一步：继承模型基类并指定表名

```python
class Lab(Base):
    __tablename__ = "labs"
```

Lab 是数据库模型，Base 提供 id、create_time、update_time 等公共字段。表名 labs 与 Python 类名 Lab 是不同概念。定义模型并不是自动创建前端页面或 HTTP 路由。

#### 第二步：定义字段类型和数据库列

```python
name: Mapped[str] = mapped_column(String(50), comment="名称", nullable=False)
capacity: Mapped[int] = mapped_column(Integer, comment="容量", default=0)
```

Mapped 表示 ORM 属性类型，mapped_column 配置数据库列。String(50) 是长度上限，Integer 是整数列。default=0 是模型插入默认值，不意味着可以接收任意类型。早期 Interger 拼写错误会导致模块导入失败，现已改正。

#### 第三步：理解 Mapped 与可空性的关系

```python
location: Mapped[str] = mapped_column(String(100), comment="位置")
```

当前 Mapped[str] 不包含 None，即使没明确写 nullable=False，SQLAlchemy 也会推断该列不允许 NULL。location、时间、简介、img 都有同类声明。允许为空通常应写 Mapped[str | None] 或显式配置 nullable=True；本节尚未统一修改这些数据库规则。

#### 第四步：区分空字符串与 NULL

当前页面把可不填写的简介和封面提交为 ""，它是空字符串，仍不是数据库 NULL。创建请求 schema 允许这些值为 None，则可能与当前模型约束冲突，不能把页面传空字符串理解为已经修好了数据库可空规则。

**把结果连起来：** model 决定表和列；schema 决定请求解析；两者需要一致，但不会自动互相修改。

### 2.2 可视化数据库软件与 create_all 的作用

```python
from app.models.lab import Lab

Base.metadata.create_all(bind=engine)
```

这是 main.py 中相关动作的节选，不是独立应用。先导入模型让其登记到元数据，再由 create_all 创建缺失的表。它不会迁移已有表的 NULL/NOT NULL、长度或其他列定义。

如果可视化软件只是显示 NOT NULL，可能是在展示模型建表后的结果；如果用它手动建表，则“允许 NULL/非空”选项也会影响实际表。不能只凭使用了可视化软件就认定问题由软件造成。

---

## 第三章 请求与响应：schemas/lab.py

### 3.1 LabResponse：把 ORM 对象转换成接口数据

```python
class LabResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int
    open_time: str | None = None
    close_time: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)
```

**按执行顺序拆解：**

#### 第一步：声明接口返回字段

```python
id: int
name: str
capacity: int
status: int
```

这是字段节选。它们决定接口输出结构，不是另建一张表。简介、封面等响应字段允许 None，以便读取相应记录；响应可空不代表数据库列已经可空。

#### 第二步：允许从对象属性读取

```python
model_config = ConfigDict(from_attributes=True)
```

当前 service 拿到的是 Lab ORM 对象，不是字典。from_attributes=True 允许 model_validate 从 lab.id/lab.name 等属性读取数据。

#### 第三步：构造响应模型

```python
LabResponse.model_validate(lab)
```

这是 service 中的调用节选。将数据库对象转换成响应模型后，API 放入 Response.success 的 data，再由 FastAPI 编码为 JSON。

### 3.2 LabCreateRequest：新增参数

```python
class LabCreateRequest(BaseModel):
    name: str
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int = 0
    open_time: str | None = None
    close_time: str | None = None
    status: int = 1
```

**按执行顺序拆解：**

#### 第一步：名称必填

```python
name: str
```

没有默认值，因此请求缺少 name 时返回 422，不进入新增服务。当前没有增加后端名称长度或空白校验，页面则有自己的规则，二者不能混为一谈。

#### 第二步：容量与状态提供默认值

```python
capacity: int = 0
status: int = 1
```

省略时分别使用 0、1；当前是普通 int，不限制范围。前端限制容量非负、状态 0/1，不等于 curl 绕过页面后也有这些后端约束。

#### 第三步：其他字段可省略但要注意数据库

```python
description: str | None = None
img: str | None = None
```

这是可选字段节选。未传会是 None，而 model 当前对应列仍非空；所以真实测试使用完整字段，页面也显式提供字符串。相关一致性问题留到最后的完善清单。

### 3.3 LabUpdateRequest：支持部分更新

```python
class LabUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    status: int | None = None
```

**按执行顺序拆解：**

#### 第一步：字段都提供 None 默认值

```python
name: str | None = None
capacity: int | None = None
```

更新可只传 capacity，不必每次重复名称、位置和封面。目标 ID 在 URL，不由这个请求体决定。

#### 第二步：由服务排除 None

```python
payload = data.model_dump(exclude_none=True)
```

这是 service 中的动作。未传值和显式 null 都被排除；capacity=0、status=0 仍会保留，因为它们不是 None。空对象更新不会赋新资料，通常仍返回当前记录。

---

## 第四章 业务层：分页、新增、更新、删除

### 4.1 get_lab_page_list：按名称筛选，再分页

```python
def get_lab_page_list(
    db: Session, page: int, page_size: int, keywords: str | None = None
):
    # select * from lab where name like "计算机实验室"
    query = db.query(Lab)
    if keywords:
        query =query.filter(Lab.name.ilike(f"%{keywords}%"))
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
```

**按执行顺序拆解：**

#### 第一步：创建查询并按名称筛选

```python
query = db.query(Lab)
if keywords:
    query = query.filter(Lab.name.ilike(f"%{keywords}%"))
```

query 是 SQLAlchemy Query 对象，尚不是结果列表。keywords 非空才加条件。当前只查实验室名称，不是用户模块的账号或姓名双字段搜索，因此不需要复制 or_ 条件。

#### 第二步：分页前统计匹配总数

```python
total = query.count()
```

总数反映所有符合条件的记录，而不是当前页条数。之后增加 offset/limit 不会改变这个已经得到的整数。

#### 第三步：按 ID 降序再取当前页

```python
items = query.order_by(Lab.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
```

这行把原链式结构写到一行说明顺序：先排序，再跳过前面记录，再限制本次条数，all 执行并返回 list[Lab]。先 limit/offset 再 order_by 会触发之前课程遇到的错误。

#### 第四步：包装分页结果

```python
return PageResponse(list=[LabResponse.model_validate(item) for item in items], total=total)
```

每个 ORM 对象转换为响应模型，列表放在 list，总数放在 total。API 外面还有统一响应层，所以前端读 res.data.list 与 res.data.total。

**把结果连起来：** 关键词 → Query → count 总数 → 排序分页 → ORM 列表 → 分页响应。

### 4.2 create_lab：查重与字典解包

```python
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
```

**按执行顺序拆解：**

#### 第一步：按名称判断是否已经存在

```python
exist = db.query(Lab).filter(Lab.name == data.name).first()
if exist:
    raise BusinessException(message="实验室已存在")
```

first 返回首条匹配对象或 None，找到就中断创建。这里按名称完全相等查重，不是模糊查询，也不代表数据库已经有唯一约束。

#### 第二步：将模型转字典并解包给 ORM

```python
lab = Lab(**data.model_dump())
```

model_dump 得到类似 {"name":"测试实验室","capacity":20,...} 的字典；** 将键值展开为 Lab(name=...,capacity=...)。这样能少写逐字段构造，但前提是请求字段与模型属性对应。None 也会进入该字典，这是可空冲突的来源。

#### 第三步：提交并读回响应

```python
db.add(lab)
db.commit()
db.refresh(lab)
return LabResponse.model_validate(lab)
```

add 纳入会话，commit 保存，refresh 重新读取字段，最后构造响应。比如数据库生成的 id 会在返回对象中出现；不要把四个动作都理解成“保存”。

### 4.3 update_lab：排除当前记录后检查重名

```python
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
```

**按执行顺序拆解：**

#### 第一步：先确定目标存在

```python
lab = db.query(Lab).filter(Lab.id == lab_id).first()
if not lab:
    raise BusinessException(message="实验室不存在")
```

目标由 URL 传入的 lab_id 决定，不存在就停止，不会自动创建一条新实验室。

#### 第二步：只有提交了非 None 名称才查重

```python
if data.name is not None:
    exist = db.query(Lab).filter(Lab.name == data.name, Lab.id != lab_id).first()
```

两个 filter 条件用 AND 组合：名称相同，并且 ID 不是当前记录。只改容量不需要查名称；名称保持原样时也不应把自己误认为重复。这个判断要放在赋值与提交之前。

#### 第三步：重复则拒绝，否则更新非 None 字段

```python
if exist:
    raise BusinessException(message="实验室已存在")
```

这段位于名称检查分支内。随后 payload 循环只更新当前提交的有效字段。setattr(lab,field,value) 相当于按字段名执行 lab.capacity=20 等赋值。源码中循环变量写为 filed，两处一致可运行，仅是名称拼写习惯不规范。

#### 第四步：提交、刷新、返回

```python
db.commit()
db.refresh(lab)
return LabResponse.model_validate(lab)
```

更新成功才继续返回响应。若名称重复抛异常，后面的提交和成功响应不会执行。

**把结果连起来：** 查目标 → 对新名称排除自身查重 → 更新字段 → 提交 → 返回最新资料。

### 4.4 delete_lab：存在才删除

```python
def delete_lab(db: Session, lab_id: int):
    """删除"""
    
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    db.delete(lab)
    db.commit()
```

**按执行顺序拆解：**

#### 第一步：查询并处理不存在

```python
lab = db.query(Lab).filter(Lab.id == lab_id).first()
if not lab:
    raise BusinessException(message="实验室不存在")
```

重复删除同一条已删除记录时，会进入不存在分支。lab_id 是实验室 ID，不能照搬删除用户时的 current_user.id 比较。

#### 第二步：标记删除并提交

```python
db.delete(lab)
db.commit()
```

这是直接删除实验室表记录，不是把 status 改为 0。状态关闭仍保留记录；删除则不再能在列表中查询到。后续如果加入设备和预约关联，需要另行设计删除规则。

---

## 第五章 API 接口、模型注册与路由注册

### 5.1 API 接收参数，业务仍在 service

四个接口中 current_user 都应注解为 User，因为管理员依赖返回的是用户对象，不是实验室对象。以下是当前完整路由函数：

### 5.2 查询接口

```python
@router.get("/list")
def get_lab_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_services.get_lab_page_list(db, page, page_size, keywords)
    return Response.success(data=res)
```

**按执行顺序理解：** 接收 page/page_size/keywords，调用查询服务，返回分页响应。 FastAPI 先准备请求参数、数据库会话并执行 `get_current_admin`；没有管理员身份就不进入正常业务。service 抛出的异常由全局处理器转换，只有正常返回才执行 Response.success。

### 5.3 新增接口

```python
@router.post("")
def create_lab(
    data: LabCreateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_services.create_lab(db, data)
    return Response.success(data=res)
```

**按执行顺序理解：** 接收 LabCreateRequest，管理员验证通过后创建。 FastAPI 先准备请求参数、数据库会话并执行 `get_current_admin`；没有管理员身份就不进入正常业务。service 抛出的异常由全局处理器转换，只有正常返回才执行 Response.success。

### 5.4 更新接口

```python
@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    data: LabUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = lab_services.update_lab(db, data, lab_id)
    return Response.success(data=res)
```

**按执行顺序理解：** 从路径取得整数 lab_id，请求体用 LabUpdateRequest，传参顺序是 db、data、lab_id。 FastAPI 先准备请求参数、数据库会话并执行 `get_current_admin`；没有管理员身份就不进入正常业务。service 抛出的异常由全局处理器转换，只有正常返回才执行 Response.success。

### 5.5 删除接口

```python
@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    lab_services.delete_lab(db, lab_id)
    return Response.success()
```

**按执行顺序理解：** 只需路径 ID，不需要新增模型作为请求体；删除成功返回 data:null。 FastAPI 先准备请求参数、数据库会话并执行 `get_current_admin`；没有管理员身份就不进入正常业务。service 抛出的异常由全局处理器转换，只有正常返回才执行 Response.success。

### 5.6 路由必须加入总路由

```python
from app.api.lab import router as lab_router

api = APIRouter(prefix="/api")
api.include_router(lab_router)
```

这是 api/__init__.py 的相关节选，其他 auth/user/files 路由仍保留。总前缀 /api、实验室前缀 /lab 与函数子路径组合，形成下表。仅在 main.py 导入 Lab 不能注册这些接口。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /api/lab/list | 分页和关键词查询 |
| POST | /api/lab | 新增 |
| PUT | /api/lab/{lab_id} | 编辑 |
| DELETE | /api/lab/{lab_id} | 删除 |

源码保存不代表旧进程已经加载。新增接口返回 404 时，查看 `/docs` 或 `/openapi.json` 的实际接口清单；必要时重启后端。HTTP 404 路由不存在与业务响应“实验室不存在”不是同一问题。

---

## 第六章 前端 API：只保留实验室相关请求

### 6.1 查询

```javascript
export function getLabPageList(params) {
  return request({
    url: '/api/lab/list',
    method: 'get',
    params
  })
}
```

**这段代码怎样执行：** 形参 params 接收页码、条数、关键词。Axios 配置中的 params 将它们放在 URL 查询字符串；method=get 不提交实验室 JSON 请求体。 四个函数都复用公共 request，自动携带 token、处理响应；本身不直接操作数据库。

### 6.2 新增

```javascript
export function createLabApi(data) {
  return request({
    url: '/api/lab',
    method: 'post',
    data
  })
}
```

**这段代码怎样执行：** 形参 data 接收表单数据，POST 的 data 放在 JSON 请求体。return 把 Promise 交给页面，页面可 await 获取拦截器处理后的结果。 四个函数都复用公共 request，自动携带 token、处理响应；本身不直接操作数据库。

### 6.3 编辑

```javascript
export function updateLabApi(labId, data) {
  return request({
    url: `/api/lab/${labId}`,
    method: 'put',
    data
  })
}
```

**这段代码怎样执行：** labId 用模板字符串拼 URL，data 是修改内容。ID 与数据不能传反。注意大写 Lab 是函数命名的一部分，小写 lab 是实际路径。 四个函数都复用公共 request，自动携带 token、处理响应；本身不直接操作数据库。

### 6.4 删除

```javascript
export function deleteLabApi(labId) {
  return request({
    url: `/api/lab/${labId}`,
    method: 'delete'
  })
}
```

**这段代码怎样执行：** 只传 labId，发送 DELETE，不需要 data。不要复制用户 API 时保留未定义变量或 /api/user 路径。 四个函数都复用公共 request，自动携带 token、处理响应；本身不直接操作数据库。

---

## 第七章 Lab.vue：列表展示与页面状态

### 7.1 列表列项

```vue
<el-table-column prop="name" label="实验室名称" />
<el-table-column prop="location" label="位置" />
<el-table-column prop="capacity" label="容量（人）" />
<el-table-column prop="description" label="简介" />
<el-table-column label="封面">
  <template #default="{ row }">
    <img v-if="row.img" :src="row.img" :alt="row.name + '封面'" />
    <span v-else>暂无封面</span>
  </template>
</el-table-column>
```

这是列表结构节选，实际还包括开放时间、状态、操作列、列宽和省略提示。每个 tableData 对象对应一行，prop 读取普通字段；封面等复杂内容用默认插槽拿到 row。封面是 img，不能再读 avatar。相对 /uploads/... 地址在开发环境通过 Vite 代理访问后端，图片样式使用 object-fit:cover 保持展示区域。

```vue
<el-tag :type="row.status === 1 ? 'success' : 'danger'">
  {{ row.status === 1 ? '开放' : '关闭' }}
</el-tag>
```

实验室状态文案改为开放/关闭，含义不再是用户的正常/禁用。后端 LabResponse 返回数字 status，页面用严格比较判断。

### 7.2 响应式状态与空表单

```javascript
const params = reactive({ page: 1, pageSize: 10, keywords: '' })
const tableData = ref([])
const total = ref(0)
const loading = ref(false)
const formRef = ref()
const dialogVisible = ref(false)
const formLoading = ref(false)
const coverUploading = ref(false)
```

params 保存查询条件，tableData/total 保存查询结果，loading 控制列表遮罩，formRef 引用表单实例，dialogVisible 控制弹窗，formLoading 控制保存状态，coverUploading 表示文件上传中。列表、保存、上传是不同操作，不能只用一个 loading 混在一起。

```javascript
const createEmptyForm = () => ({
  id: null,
  name: '',
  location: '',
  capacity: 0,
  open_time: '08:00',
  close_time: '18:00',
  description: '',
  img: '',
  status: 1
})
```

```javascript
const form = reactive(createEmptyForm())
```

**按执行顺序拆解：**

#### 第一步：每次调用产生默认字段

```javascript
id: null,
open_time: "08:00",
close_time: "18:00"
```

这是对象属性节选。空 ID 表示新增，开始/结束提供方便填写的默认值；它们都是前端默认，不会自动插入数据库。

#### 第二步：可不填文本使用空字符串

```javascript
description: "",
img: ""
```

页面不要求必须上传封面或填写简介，但保存时仍发送字符串，以配合当前模型非空列。img 是 URL 字符串，不是图片二进制。

#### 第三步：建立响应式编辑对象

```javascript
const form = reactive(createEmptyForm())
```

调用我们自己的工厂函数取得对象，交给 Vue reactive，输入框通过 v-model 同步。重置时仍要修改原对象，保持已有绑定。

### 7.3 load：查询实验室并更新列表

```javascript
const load = async () => {
  loading.value = true
  try {
    const res = await getLabPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords.trim()
    })
    if (res.code === 200) {
      tableData.value = res.data?.list ?? []
      total.value = res.data?.total ?? 0
    }
  } catch (error) {
    console.error('加载实验室列表失败', error)
  } finally {
    loading.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：显示列表加载状态

```javascript
loading.value = true
```

ref 在脚本里通过 .value 写入，表格 v-loading 读取后显示遮罩。此时只是状态变化，还没拿到数据。

#### 第二步：读取当前条件并请求

```javascript
const res = await getLabPageList({ page: params.page, page_size: params.pageSize, keywords: params.keywords.trim() })
```

前端 pageSize 映射为后端 page_size；关键词去两端空白，空关键词代表不筛选。await 等响应，不会阻塞整个浏览器；res 已由公共拦截器变为业务 JSON。

#### 第三步：业务成功时替换列表与总数

```javascript
tableData.value = res.data?.list ?? []
total.value = res.data?.total ?? 0
```

?. 安全读取可空 data，?? 在结果为 null/undefined 时提供空数组或 0。更新响应式值后 Vue 自动刷新表格与分页，不需要整页刷新。

#### 第四步：异常记录与结束状态

```javascript
catch (error) {
  console.error("加载实验室列表失败", error)
} finally {
  loading.value = false
}
```

公共拦截器负责请求失败提示，此处记录调用上下文并保证遮罩收起。当前 catch 不再抛出，因此 await load 会等待查询结束，但不会把已捕获错误重新抛给保存函数。

**把结果连起来：** 页面挂载、搜索与翻页均可复用同一个 load。

### 7.4 搜索与首次加载

```javascript
const handleSearch = async () => {
  params.page = 1
  await load()
}

onMounted(load)
```

搜索先把页码重置为 1，再等待 load，避免新关键词结果较少而仍查高页码。onMounted 是 Vue 钩子，挂载后调用我们写的 load；onMounted(load) 传入函数引用，并不是注册时立即写成 load()。翻页仍由 el-pagination 的 current-change 触发。

---

## 第八章 表单与校验：TimePicker 和数字输入

### 8.1 开放时间选择器

```vue
<el-form-item label="开始时间" prop="open_time">
  <el-time-picker
    v-model="form.open_time"
    format="HH:mm"
    value-format="HH:mm"
    placeholder="请选择开放开始时间"
    @change="validateOpeningHours"
  />
</el-form-item>
<el-form-item label="结束时间" prop="close_time">
  <el-time-picker
    v-model="form.close_time"
    format="HH:mm"
    value-format="HH:mm"
    placeholder="请选择开放结束时间"
  />
</el-form-item>
```

**按执行顺序拆解：**

#### 第一步：用 v-model 绑定两个业务字段

```vue
v-model="form.open_time"
v-model="form.close_time"
```

这是两个不同控件的属性节选。用户选择后，值分别写进开始和结束字段，后续提交时就能与后端 open_time/close_time 对应。

#### 第二步：区分显示格式和绑定值格式

```vue
format="HH:mm"
value-format="HH:mm"
```

format 控制显示小时分钟，value-format 让绑定值使用字符串，例如 "08:00"，而不是默认日期对象。后端当前使用字符串字段，因此指定两种格式十分重要。

#### 第三步：开始变化后复查结束时间

```vue
@change="validateOpeningHours"
```

例如原来 08:00～18:00 有效，开始改为 19:00 后结束值没变，需要主动重新验证结束时间，不能只等用户再次点击结束控件。

**把结果连起来：** 选择 → 字符串写入 form → 按同一天的开始/结束顺序校验 → 提交。

### 8.2 validateCloseTime：为什么字符串能比较时间

```javascript
const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/
```

```javascript
const validateCloseTime = (rule, value, callback) => {
  if (!value || !timePattern.test(value)) {
    callback(new Error('请选择有效的结束时间'))
  } else if (timePattern.test(form.open_time) && value <= form.open_time) {
    callback(new Error('结束时间必须晚于开始时间'))
  } else {
    callback()
  }
}
```

**按执行顺序拆解：**

#### 第一步：先检查值和格式

```javascript
if (!value || !timePattern.test(value)) {
  callback(new Error("请选择有效的结束时间"))
}
```

value 是结束时间。正则限制为 00:00～23:59，小时分钟都补齐两位。无值或格式不正确就通过 callback 报告失败。

#### 第二步：格式正确后比较同日先后

```javascript
value <= form.open_time
```

只有标准 HH:mm 字符串才按这里比较："09:00" 小于 "18:00"。代码先确认开始值格式有效，再拒绝结束不晚于开始的情况；因此当前规则不表示跨夜开放，如 22:00～02:00 会被拒绝。

#### 第三步：报告通过

```javascript
callback()
```

没有错误参数表示校验成功。每条执行分支只调用一次 callback，函数本身不发请求。

```javascript
const validateOpeningHours = () => {
  if (formRef.value && form.close_time) {
    formRef.value.validateField('close_time').catch(() => {})
  }
}
```

开始时间变化后，若表单实例和结束值都存在，调用 validateField 只检查 close_time。校验失败已经由表单显示，所以 catch 在这里正常结束，不需要额外弹一次错误。

### 8.3 完整 rules 与数字类型

```javascript
const rules = {
  name: [
    { required: true, whitespace: true, message: '请输入实验室名称', trigger: 'blur' },
    { max: 50, message: '实验室名称不能超过50个字符', trigger: 'blur' }
  ],
  location: [
    { required: true, whitespace: true, message: '请输入实验室位置', trigger: 'blur' },
    { max: 100, message: '位置不能超过100个字符', trigger: 'blur' }
  ],
  capacity: [
    { required: true, type: 'number', message: '请输入容量', trigger: 'change' },
    { type: 'integer', min: 0, message: '容量必须是非负整数', trigger: 'change' }
  ],
  open_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
    { pattern: timePattern, message: '时间格式应为HH:mm', trigger: 'change' }
  ],
  close_time: [{ validator: validateCloseTime, trigger: 'change' }],
  description: [{ max: 500, message: '简介不能超过500个字符', trigger: 'blur' }],
  img: [{ max: 100, message: '封面地址不能超过100个字符', trigger: 'change' }],
  status: [
    { required: true, type: 'enum', enum: [0, 1], message: '请选择开放状态', trigger: 'change' }
  ]
}
```

**按执行顺序拆解：**

#### 第一步：名称与位置不可只有空白

```javascript
name: [{ required: true, whitespace: true, message: "请输入实验室名称", trigger: "blur" }]
```

这是规则节选。whitespace 拒绝只输入空格，长度上限与数据库列对应。输入框的 maxlength 改善交互，rules 则参与保存前的校验。

#### 第二步：容量明确使用数字与整数规则

```javascript
capacity: [
  { required: true, type: "number", message: "请输入容量", trigger: "change" },
  { type: "integer", min: 0, message: "容量必须是非负整数", trigger: "change" }
]
```

el-input-number 绑定的是数字，不是普通字符串。必填规则要与类型对应，后续再要求整数且非负；0 是合法值。检查过程中发现缺少 number 类型会让有效容量错误报必填，已修正。

#### 第三步：限制状态和文本长度

status 使用 enum 只允许 0/1；简介最多 500 字符，封面 URL 最多 100 字符。这里检查的是 URL 长度，不是图片文件字节数，图片大小由上传前函数检查。

**把结果连起来：** 页面规则和后端 schema 是两层独立校验，当前后端尚未同步所有前端约束。

---

## 第九章 封面上传：复用头像的两步模式

### 9.1 模板连接选择、上传与预览

```vue
<el-upload
  class="cover-uploader"
  :http-request="handleCoverUpload"
  :before-upload="beforeCoverUpload"
  :show-file-list="false"
  :disabled="coverUploading || formLoading"
  accept="image/jpeg,image/png,image/gif,image/webp"
>
  <img v-if="form.img" :src="form.img" alt="实验室封面预览" />
  <span v-else>上传封面</span>
</el-upload>
```

这是保留核心绑定的模板节选；实际页面还包含上传加载遮罩、Plus 图标、样式提示和移除按钮。http-request 指定自定义上传，before-upload 先检查文件，accept 限定选择提示。预览使用 form.img，表格使用 row.img，两者角色不同但字段相同。

### 9.2 beforeCoverUpload：先检查类型和大小

```javascript
const beforeCoverUpload = (file) => {
  const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!imageTypes.includes(file.type)) {
    ElMessage.error('封面只能上传JPG、PNG、GIF或WebP图片')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('封面大小不能超过2MB')
    return false
  }
  return true
}
```

**按执行顺序拆解：**

#### 第一步：限制浏览器报告的类型

```javascript
const imageTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"]
```

includes 检查 file.type。PDF 等非图片先提示并返回 false，阻止组件上传。浏览器 MIME 检查是交互防错，不是服务器的完整文件内容验证。

#### 第二步：按字节检查 2 MB 上限

```javascript
if (file.size > 2 * 1024 * 1024) {
  ElMessage.error("封面大小不能超过2MB")
  return false
}
```

file.size 来自浏览器 File 对象，单位为字节。界面封面限制 2 MB，后端通用上传上限为 100 MB，规则不同；不能认为前端限制会自动约束 curl。

#### 第三步：校验通过才继续

```javascript
return true
```

true 允许 el-upload 继续调用 handleCoverUpload。此时文件才进入实际请求流程。

### 9.3 uploadFileApi：复用已有上传接口

```javascript
export function uploadFileApi(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request({
    url: '/api/files/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
```

FormData 是浏览器工具，不需要从 Vue 导入。append 的键 file 与后端 UploadFile 参数对应；发送 POST /api/files/upload，返回包含 url 的业务响应。当前代码沿用已有的 multipart 配置，实际编码还需要浏览器/Axios 处理 boundary。实验室封面无需新建一套重复上传后端。

### 9.4 handleCoverUpload：URL 先写进表单

```javascript
const handleCoverUpload = async ({ file }) => {
  coverUploading.value = true
  try {
    const res = await uploadFileApi(file)
    if (res.code !== 200) {
      throw new Error(res.message || '封面上传失败')
    }
    if (!res.data?.url) {
      ElMessage.error('上传结果没有返回封面地址')
      throw new Error('缺少封面地址')
    }
    form.img = res.data.url
    return res.data
  } finally {
    coverUploading.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：解构上传选项并打开加载状态

```javascript
const handleCoverUpload = async ({ file }) => {
  coverUploading.value = true
```

组件传入上传选项对象，花括号取出 file。coverUploading 控制上传区域并禁用保存/取消等操作，避免文件还没上传就提交或把结果写进另一份新表单。

#### 第二步：等待上传并处理异常结果

```javascript
const res = await uploadFileApi(file)
```

非 200 业务码或缺少 URL 都会抛错误。普通请求错误由公共请求层提示；缺少 URL 在此显示明确提示。返回的 Promise 由 el-upload 接续处理成功/失败，不需要在函数里再手工调用一遍组件回调。

#### 第三步：更新预览并返回上传数据

```javascript
form.img = res.data.url
return res.data
```

表单 img 改变后，v-if 与 src 使预览出现。此处没有调用 createLabApi/updateLabApi，因此只是得到并暂存 URL，实验室数据库字段尚未保存。

#### 第四步：无论成败关闭上传状态

```javascript
finally {
  coverUploading.value = false
}
```

失败时也恢复按钮。此函数没有吞掉错误，Promise 拒绝交给上传组件处理；不要把 finally 当作 catch。原来的封面不会因失败被先清空。

**把结果连起来：** 选文件 → 校验 → 上传到磁盘 → 获取 URL → 表单预览 → 点击保存后关联实验室。

移除封面只将 form.img 设为 ""，之后保存才更新实验室字段，不会立即删除服务器文件；上传后取消也可能留下未关联文件，与之前头像功能的两步模式一致，后续清理策略放在完善清单。

---

## 第十章 弹窗：重置、回显与保存

### 10.1 resetForm 与 handleCreate

```javascript
const resetForm = () => {
  Object.assign(form, createEmptyForm())
}

const handleCreate = async () => {
  resetForm()
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}
```

**按执行顺序拆解：**

#### 第一步：回到实验室默认表单

```javascript
Object.assign(form, createEmptyForm())
```

清除旧 ID、名称、封面等，保留原响应式对象。否则从编辑切到新增可能残留 ID，误走更新接口。

#### 第二步：先显示，再等组件更新

```javascript
dialogVisible.value = true
await nextTick()
```

nextTick 来自 Vue，等待本次响应式变化引起的 DOM/组件更新，使懒渲染弹窗中的表单可以被引用。不是固定睡眠，也不是网络请求。

#### 第三步：清理旧校验提示

```javascript
formRef.value?.clearValidate()
```

如果表单实例已存在，就清除上一轮错误状态。这里只清校验显示，不会替代 resetForm 的数据重置。

### 10.2 handleEdit：实验室字段回显

```javascript
const handleEdit = async (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name ?? '',
    location: row.location ?? '',
    capacity: row.capacity ?? 0,
    open_time: row.open_time?.slice(0, 5) ?? '',
    close_time: row.close_time?.slice(0, 5) ?? '',
    description: row.description ?? '',
    img: row.img ?? '',
    status: row.status ?? 1
  })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}
```

**按执行顺序拆解：**

#### 第一步：先重置，再复制行资料

```javascript
id: row.id,
name: row.name ?? "",
capacity: row.capacity ?? 0,
status: row.status ?? 1
```

这是对象属性节选。?? 只在 null/undefined 时使用默认值，因此容量 0 和关闭状态 0 会被保留，不能不加区分地用 || 代替。

#### 第二步：把历史秒格式整理成分钟格式

```javascript
open_time: row.open_time?.slice(0, 5) ?? "",
close_time: row.close_time?.slice(0, 5) ?? ""
```

例如 09:00:00 取前五位变为 09:00，适配当前 TimePicker 的 HH:mm。该截取不是任意时间格式解析器，异常历史字符串仍需由校验提示用户处理。

#### 第三步：打开并清理验证状态

```javascript
dialogVisible.value = true
await nextTick()
formRef.value?.clearValidate()
```

表单 id 有值使标题显示编辑实验室。没有用户账号、密码等控件，也就不应再保留相关编辑限制或校验。

### 10.3 handleSave：只发送后端需要的字段

```javascript
const handleSave = async () => {
  if (formLoading.value || coverUploading.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  formLoading.value = true
  try {
    // 显式提交实验室字段，避免把ID或复制自用户页面的字段发送给后端。
    const data = {
      name: form.name.trim(),
      location: form.location.trim(),
      capacity: form.capacity,
      open_time: form.open_time,
      close_time: form.close_time,
      description: form.description ?? '',
      img: form.img ?? '',
      status: form.status
    }
    const res = form.id ? await updateLabApi(form.id, data) : await createLabApi(data)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success(form.id ? '实验室更新成功' : '实验室新增成功')
      await load()
    }
  } catch (error) {
    console.error('保存实验室失败', error)
  } finally {
    formLoading.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：上传/保存期间不再提交，并校验表单

```javascript
if (formLoading.value || coverUploading.value) return
const valid = await formRef.value.validate().catch(() => false)
if (!valid) return
```

上传尚未得到 URL 时不能保存；表单验证失败也提前结束。等待验证只暂停本函数后续逻辑，不阻塞浏览器。

#### 第二步：构造明确的实验室请求体

```javascript
const data = {
  name: form.name.trim(),
  location: form.location.trim(),
  capacity: form.capacity,
  open_time: form.open_time,
  close_time: form.close_time,
  description: form.description ?? "",
  img: form.img ?? "",
  status: form.status
}
```

只提交八个业务字段，ID 放在 URL 或由数据库生成。名称和位置去两端空白，空简介和封面仍发送字符串，避免当前模型非空列收到 None。不能继续沿用 createUserApi 或提交用户字段。

#### 第三步：按 ID 选择创建或更新

```javascript
const res = form.id ? await updateLabApi(form.id, data) : await createLabApi(data)
```

ID 有值走 PUT，没有走 POST。两个分支只执行一个；返回的是公共拦截器处理后的业务 JSON。

#### 第四步：成功关闭、提示并等待列表刷新

```javascript
dialogVisible.value = false
ElMessage.success(form.id ? "实验室更新成功" : "实验室新增成功")
await load()
```

这些语句位于 res.code===200 分支中。await 使保存函数等待 load 结束；load 自己处理刷新错误，因此不会因刷新失败把已经提交成功的新增说成未保存。

#### 第五步：处理请求异常并收尾

```javascript
finally {
  formLoading.value = false
}
```

保存请求异常由 catch 记录、公共请求层提示；finally 恢复保存按钮。这里没有改变其他用户页面的既有处理方式。

**把结果连起来：** 校验 → 构造字段 → 选 POST/PUT → 成功关闭 → 刷新 → 恢复按钮。

### 10.4 handleDelete：确认后再删除

```javascript
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除实验室[${row.name}]？`, '确认删除', { type: 'warning' })
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除确认失败', error)
    }
    return
  }
  try {
    const res = await deleteLabApi(row.id)
    if (res.code === 200) {
      ElMessage.success('实验室删除成功')
      if (tableData.value.length === 1 && params.page > 1) {
        params.page -= 1
      }
      await load()
    }
  } catch (error) {
    console.error('删除实验室失败', error)
  }
}
```

**按执行顺序拆解：**

#### 第一步：先等待确认框

```javascript
await ElMessageBox.confirm(`确认删除实验室[${row.name}]？`, "确认删除", { type: "warning" })
```

提示使用实验室名称，row 是表格当前行。确认才往后执行；取消或关闭进入第一个 catch 后 return，所以不会发 DELETE。

#### 第二步：调用实验室删除接口

```javascript
const res = await deleteLabApi(row.id)
```

ID 来自实验室记录，不是用户 ID；后端管理员依赖与目标存在检查仍会执行。业务非成功不显示删除成功。

#### 第三步：处理当前页仅一条数据的情况

```javascript
if (tableData.value.length === 1 && params.page > 1) {
  params.page -= 1
}
await load()
```

成功删除后，若本页只剩该条且不是第一页，先回前一页再查询，避免停留在刚被删空的一页。实际浏览器分页联动还需要结合组件事件验证，不能只凭模拟检查声称所有并发分页场景都已覆盖。

#### 第四步：分开处理确认失败和请求失败

第一个 catch 负责取消/关闭等确认结果，第二个 catch 负责删除请求异常；取消不需要弹删除失败。load 内部还有自己的请求异常处理。

---

## 第十一章 菜单权限与前后端配合

```vue
<el-menu-item index="/manager/lab" v-if="userInfo?.role === 'admin'">
  <el-icon><House /></el-icon>
  <span>实验室管理</span>
</el-menu-item>
```

**按执行顺序拆解：**

#### 第一步：根据共享角色显示入口

```vue
v-if="userInfo?.role === 'admin'"
```

只有管理员渲染此菜单，学生看不到入口。?. 允许用户状态尚为空。它是当前角色判断，不是 Lab.vue 文件被删除。

#### 第二步：区分菜单隐藏与服务器授权

当前路由仍定义 /manager/lab，学生手工输入路径不等于得到数据；实验室四个后端接口都使用 get_current_admin，真实 curl 学生测试已被拒绝。菜单控制只是界面行为，不替代后端鉴权。

```javascript
{ path: 'lab', name: 'Lab', component: () => import('@/views/Lab.vue') }
```

这是 /manager 的子路由，完整页面路径为 /manager/lab，与后端 /api/lab 不是同一用途。本节还按之前排错建议补上了 equ 子路由，使设备占位页有对应路径；这不表示设备管理业务已经完成。

---

## 第十二章 课堂补充：个人资料排除 role 与 status

### 12.1 从暂存问题到当前实现

本文件最初在 2026-11-06 只暂存这个问题。最初 UserUpdateRequest 包含 role/status，个人资料服务又循环更新全部非 None 字段，因此正常登录的普通用户可能修改自己的角色和状态。当前源码已经采用下面的排除方案，不能再写成“只是讨论、尚未实施”。

```python
def update_user_info(db:Session,user:User,data:UserUpdateRequest):
    user_dict=data.model_dump(exclude_none=True,exclude={"role","status"})
    for field,value in user_dict.items():
        setattr(user,field,value)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
```

**按执行顺序拆解：**

#### 第一步：排除两种不应个人修改的字段

```python
user_dict = data.model_dump(exclude_none=True, exclude={"role", "status"})
```

exclude_none 忽略 None；exclude 无论值是什么都移除 role/status。二者共同决定后面循环能够写哪些字段。即使请求模型仍接受这两个键，它们也不进入个人资料更新字典。

#### 第二步：剩余资料继续正常保存

```python
for field, value in user_dict.items():
    setattr(user, field, value)
```

例如同时提交 name 与 role，名称可更新，role 被忽略。这里不是返回“无权限修改角色”，而是静默忽略不允许更新的字段。

#### 第三步：管理员更新保持独立

管理员的 update_user 仍使用自己的原更新字典，不排除 role/status。不能把个人资料的限制复制到所有管理员操作中；后续仍可拆分请求模型以表达不同权限。

**把结果连起来：** 当前个人资料接口的批量赋值先过滤敏感字段，普通资料不受影响。

### 12.2 本次核对的证据

源码第 15 行已包含 exclude。本次用 SQLite 内存数据库检查：普通用户资料请求同时提交新名称、role=admin、status=0 后，名称更新，角色仍为 student，状态仍为 1；管理员更新函数仍可改变角色/状态。此项是内存服务层验证，没有向真实用户发送提权或禁用请求，也不等同于新的真实 HTTP 全链路验证。

---

## 第十三章 真实测试、页面创建与本次检查

### 13.1 实验室真实 curl 测试

2026-11-09 已实际调用本机后端，45 项接口与数据断言全部通过；其中包含测试准备和基线核对，并不是 45 种独立 HTTP 接口。报告摘要如下，不保存实际 token 或登录密码。

| 场景 | HTTP / 业务码 | 结果 |
|---|---|---|
| 运行服务已注册实验室四个接口 | 数据/路由核对 | 通过 |
| 管理员登录（测试准备） | 200 / 200 | 通过 |
| 测试请求使用管理员身份 | 数据/路由核对 | 通过 |
| 测试名称未占用原有实验室名称 | 数据/路由核对 | 通过 |
| 完整字段新增实验室A | 200 / 200 | 通过 |
| 新增返回字段正确 | 数据/路由核对 | 通过 |
| 重复新增被拒绝 | 200 / 500 | 通过 |
| 分页查询成功 | 200 / 200 | 通过 |
| 分页列表和总数有效 | 数据/路由核对 | 通过 |
| 关键词搜索定位新建实验室 | 数据/路由核对 | 通过 |
| 更新容量与关闭状态 | 200 / 200 | 通过 |
| 只更新提交的字段 | 数据/路由核对 | 通过 |
| 提交原名称不误报重名 | 200 / 200 | 通过 |
| 新增实验室B供重名测试 | 200 / 200 | 通过 |
| 改成其他已有名称被拒绝 | 200 / 500 | 通过 |
| 更新重名失败后原名称不变 | 数据/路由核对 | 通过 |
| 空对象更新不改变资料 | 200 / 200 | 通过 |
| 空对象更新字段保持一致 | 数据/路由核对 | 通过 |
| null字段更新被忽略 | 200 / 200 | 通过 |
| null没有清空位置 | 数据/路由核对 | 通过 |
| 缺少必填name返回422 | 422 / 422 | 通过 |
| 非数字ID返回422 | 422 / 422 | 通过 |
| 不存在ID未被实际占用 | 数据/路由核对 | 通过 |
| 更新不存在实验室被拒绝 | 200 / 500 | 通过 |
| 删除不存在实验室被拒绝 | 200 / 500 | 通过 |
| 无token不能查询 | 401 / 401 | 通过 |
| 无token不能新增 | 401 / 401 | 通过 |
| 无token不能修改 | 401 / 401 | 通过 |
| 无token不能删除 | 401 / 401 | 通过 |
| 无效token不能查询 | 401 / 401 | 通过 |
| 无效token不能新增 | 401 / 401 | 通过 |
| 无效token不能修改 | 401 / 401 | 通过 |
| 无效token不能删除 | 401 / 401 | 通过 |
| 已有学生账号登录（测试准备） | 200 / 200 | 通过 |
| 权限测试使用学生身份 | 数据/路由核对 | 通过 |
| 学生不能查询 | 200 / 403 | 通过 |
| 学生不能新增 | 200 / 403 | 通过 |
| 学生不能修改 | 200 / 403 | 通过 |
| 学生不能删除 | 200 / 403 | 通过 |
| 拒绝请求未创建实验室或修改容量 | 数据/路由核对 | 通过 |
| 管理员删除实验室A | 200 / 200 | 通过 |
| 删除后按名称查不到A | 数据/路由核对 | 通过 |
| 重复删除同一ID被拒绝 | 200 / 500 | 通过 |
| 清理测试实验室：curl_lab_20261109_8f89c2_B | 200 / 200 | 通过 |
| 所有测试记录已清理且原有实验室资料未变 | 数据/路由核对 | 通过 |

专用测试实验室 A/B 已全部清理，测试时原有实验室资料与基线一致。这些真实 curl 检查针对后端，不代替浏览器上传与表单校验检查。业务“实验室已存在/不存在”在当前处理器下可能使用 HTTP 200 + 业务码 500，不能只看 HTTP 200 就认定操作成功。

### 13.2 用户实际创建与数据库核对

页面改造后，用户实际创建了一条“数学实验室”。随后只读查询确认数据库包含 ID 3 的记录，位置为“教学楼 A座103”，容量 20，开放时间 08:00～19:00，状态 1，简介为空字符串，img 保存了 /uploads/ 下的 JPG 路径。当时总数为 1。这说明该次资料和封面路径已经落库；不是保证数据库以后一直只有这条，也不是本次文档整理又创建了一次。

真实上传图片属于本地运行数据，按 .gitignore 排除，不把用户上传文件或数据库导出一并推送。新克隆代码的环境不会自动拥有这条记录或图片。

### 13.3 前端与模型兼容检查

前端生产构建通过。模拟 API 检查使用实际 Vue 响应式对象和表单校验器，覆盖：

- 新增默认值、编辑回显、清理校验、只提交实验室字段。
- 非空白名称、必填位置、容量非负整数、状态值和文本长度。
- 时间格式、结束晚于开始、编辑时秒格式转为分钟格式。
- 图片类型/大小、上传成功/失败、上传中阻止保存。
- 创建/更新调用、取消和关闭不删除、删除后页码回退、关键词与分页参数。

前端生成的提交对象还通过了 LabCreateRequest、LabUpdateRequest 解析检查。模拟请求没有写真实数据，不等同于浏览器中逐个场景都已手工操作。前端构建有既有的较大资源块提示，不影响本次构建完成。

### 13.4 可复现的 curl 命令

使用新建测试记录，替换账号密码/token 占位值，确认服务加载了实验室接口。写操作完成后清理自己的测试记录，不使用当前真实实验室 ID 演示删除。

```bash
BASE_URL='http://localhost:8000'

curl -sS -X POST "$BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"你的管理员账号","password":"当前密码"}'

ADMIN_TOKEN='替换为登录返回的token'

curl -sS -i -X POST "$BASE_URL/api/lab" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"lesson15_demo","location":"测试楼101","capacity":20,"open_time":"08:00","close_time":"18:00","description":"","img":"","status":1}'

LAB_ID=替换为此次新增返回的数字ID

curl -sS -i -G "$BASE_URL/api/lab/list" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=10' \
  --data-urlencode 'keywords=lesson15_demo'

curl -sS -i -X PUT "$BASE_URL/api/lab/$LAB_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"capacity":30,"status":0}'

# 最后清理测试记录，确认 LAB_ID 指向刚创建的测试实验室。
curl -sS -i -X DELETE "$BASE_URL/api/lab/$LAB_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 第十四章 本课踩坑记录

| 问题 | 原因 | 当前处理/结论 |
|---|---|---|
| Interger 导入失败 | Integer 拼写错 | 模型导入与两处列类型已更正 |
| 实验室接口 404 | 未 include_router | 总路由已导入并注册 lab_router |
| current_user 注解成 Lab | 把业务实体与登录用户混淆 | 四个依赖参数都改为 User |
| 更新名称与其他记录重复 | 只有新增检查重名 | 更新先查目标，再用 name 相同且 id 不同检查 |
| 保留原名称也报重复 | 查重不排除自身 | 使用 Lab.id != lab_id |
| 可选字段插入失败 | schema 允许 None，Mapped[str] 列非空 | 已记录一致性问题；页面提交字符串，未擅自迁移数据库 |
| Lab.vue 仍调用用户接口 | 复制后没有改导入和函数 | 改为 lab.js 四个 API |
| img 判断但 avatar 显示 | 图片字段复制不完整 | 封面统一使用 img |
| 实验室仍有账号/角色/密码表单 | 只改标题没改业务字段 | 删除用户字段，增加位置、容量、时间、封面、简介 |
| 时间提交为日期对象或不对应字段 | 没区分显示与绑定格式 | TimePicker 同时配置 format/value-format 为 HH:mm |
| 有效容量被必填规则拒绝 | 数字字段必填规则缺少类型 | 明确 type:number，再检查 integer/min |
| 学生看不到管理菜单 | 管理入口按角色隐藏 | 这是目标行为；后台同时限制管理员访问 |
| 新增数据库 ID 从 3 开始 | 前面的测试曾创建并删除记录 | 自增 ID 不保证连续，不影响新增是否成功 |

---

## 常见问题

**Q1：User.vue 和 Lab.vue 很像，为什么不能直接复用全部内容？**

相同的是列表与弹窗的交互模式，不同的是数据字段、校验、接口与业务含义。只换 User/Lab 字符串会遗漏 avatar/img、角色、时间、上传等差异。

**Q2：name 搜索的 curl 为什么使用 keywords？**

name 是数据库字段，keywords 是接口查询参数。服务拿 keywords 构建 Lab.name 的条件；请求参数叫错可能被忽略，导致返回全部记录。

**Q3：只改模型，数据库里的非空属性会跟着变吗？**

不会。create_all 创建缺失表，不自动迁移已有列；模型、实际表结构与请求规则需要分别核对。

**Q4：上传封面后没保存，刷新会怎样？**

文件可能已在 uploads，但实验室 img 尚未更新，页面重新读取数据库时不会保留这次尚未保存的关联。它与头像上传的两步模式相同。

**Q5：时间用字符串比较可靠吗？**

本页只比较通过格式校验、补齐两位的同日 HH:mm。不要把这种比较推广成跨日期、时区或跨夜开放的通用时间逻辑。

**Q6：普通用户菜单隐藏了，还需要后端鉴权吗？**

需要。用户可以手工输入 URL 或 curl；真正的数据权限由 get_current_admin 控制，菜单只是展示。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| Mapped | SQLAlchemy ORM 属性的类型声明，也参与可空性推断 |
| nullable | 数据库列是否允许 NULL |
| create_all | 创建元数据中缺失的表，不自动迁移旧列 |
| model_dump | Pydantic 模型转换为字典 |
| ** 字典解包 | 将字典键值展开成函数的关键字参数 |
| from_attributes | 允许响应模型从 ORM 对象属性读取值 |
| TimePicker | Element Plus 的时间选择控件 |
| format | 控制时间显示格式 |
| value-format | 控制时间绑定值格式 |
| nextTick | 等待 Vue 当前一轮响应式更新完成 |
| clearValidate | 清除表单已有校验状态，不重置数据 |
| FormData | 浏览器用于文件/表单传输的容器 |
| ?? | 值为 null/undefined 时才使用备用值 |
| exclude | 指定 model_dump 不输出某些字段 |

---

## 本章自检清单

- [ ] 能列出实验室字段，并指出哪些用户字段应删除
- [ ] 能解释 model、schema、API、service 与前端页面的关系
- [ ] 能解释 Mapped[str] 与 Mapped[str | None] 的可空性区别
- [ ] 知道 create_all 不会自动修改已建表的列
- [ ] 能展开 Lab(**data.model_dump()) 的含义
- [ ] 能解释更新查重为什么排除自身
- [ ] 能说出四个实验室接口的路径、方法和权限
- [ ] 能解释 format 和 value-format 为什么都设置
- [ ] 能说清当前时间规则是同日开始/结束
- [ ] 能解释容量校验中的 number、integer 和 min
- [ ] 能区分列表 loading、formLoading 和 coverUploading
- [ ] 能解释 nextTick 后清校验与重置数据的区别
- [ ] 能口述封面选择、上传、预览、保存的完整过程
- [ ] 知道 img 保存 URL，实际图片不存进该字符串列
- [ ] 能解释编辑回显为何用 ?? 保留合法的 0
- [ ] 能解释保存时为什么显式构造 data
- [ ] 能说明取消删除不会发送请求
- [ ] 能区分菜单隐藏、路由访问与后端鉴权
- [ ] 知道个人资料 exclude 方案已经实施，但尚未拆分请求模型
- [ ] 能区分真实 curl、内存数据库、模拟前端与用户实际创建的证据

---

## 附录：课程结束后统一完善

整体框架仍未完成。以下项目按既定安排记录在文档最后，等全部课程结束后统一评估，不在本次整理与上传时修改业务代码。文件行号对应本节整理时版本，未来改动前重新定位。

| 位置 | 后续事项 | 当前边界与方向 |
|---|---|---|
| backend/app/models/lab.py 第 11、13～16 行；schemas/lab.py 第 23～28 行 | 模型、schema 与实际数据库可空规则统一 | 页面传空字符串只规避当前入口，不等于后端全部可选字段已经一致 |
| backend/app/schemas/lab.py 第 21、32 行开始 | 后端参数校验补齐 | 名称长度/空白、容量范围、status 取值、时间格式与先后目前主要由前端限制 |
| backend/app/api/lab.py 第 20、21 行 | 分页边界 | 后续明确 page>=1、page_size 上限 |
| backend/app/services/lab_services.py 第 32、52 行及模型名称列 | 并发重名与数据库约束 | 当前服务查重不等于数据库唯一约束，后续决定名称唯一规则 |
| frontend/src/views/Lab.vue 第 210 行 | 开放时间业务扩展 | 跨夜、多时段、预约日历等留待实际业务需要时设计 |
| frontend/src/views/Lab.vue 第 314 行及后端上传服务 | 图片处理和资源清理 | 未保存关联、替换/移除后的旧图清理与内容校验尚未完善 |
| backend/app/services/lab_services.py 第 66 行 | 关联数据删除规则 | 引入设备/预约后再确定禁止删除、级联或软删除策略 |
| backend/app/services/user_services.py 第 15 行；schemas/user.py 第 19 行 | 请求模型分离 | 当前 exclude 已拦住个人角色/状态更新；可后续拆分个人/管理员请求模型 |
| frontend/src/router/index.js 第 27 行 | 页面角色控制 | 当前菜单隐藏与后端校验有效，路由守卫尚未按角色单独限制页面 |
| frontend/src/views/Lab.vue 第 332 行等异步入口 | 交互并发完善 | 后续结合浏览器实测统一重复提交、请求竞态、分页联动等细节 |

前面课程笔记保留的是各节当时的状态。本节新采用的 Lab.vue 表单处理与个人资料排除，不表示已自动修改所有旧页面或所有旧待办。

