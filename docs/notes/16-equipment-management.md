# 开发实验室设备管理功能(重点:关联查询)

> 对应课程:第 16 节
> 对应项目:`agent-lab/lab-system-agent`
> 涉及文件:
> - 后端:`app/models/equipment.py`、`app/schemas/equipment.py`、`app/api/equipment.py`、`app/services/equipment_services.py`
> - 前端:`src/api/equipment.js`、`src/views/Equ.vue`
> 本课重点:**表关联(ForeignKey + relationship)、关联查询(joinedload)、N+1 问题**
> 阅读时间:约 35 分钟

---

## 第零章 这节课在干什么

实验室管理之后,加一个"设备管理":设备属于某个实验室(多对一)。本课的核心新知识点是**关联**:

```
labs 表(实验室)              equipments 表(设备)
┌──────────────┐            ┌──────────────────────┐
│ id  name ... │ ◄────────── │ lab_id(外键) name ... │
└──────────────┘   一对多    └──────────────────────┘
  一个实验室有多个设备
```

新挑战:设备列表要**显示实验室名字**,但设备表里只有 `lab_id`,名字在另一张表里 → 需要**关联查询**。

---

## 第一章 表关联:模型层(models/equipment.py)

```python
class Equipment(Base):
    __tablename__ = "equipments"

    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id"), comment="所属实验室")
    name: Mapped[str] = mapped_column(String(50))
    # ... 其他字段

    lab: Mapped[Lab] = relationship()     # ← 关联的关键
```

两个新概念:

| 概念 | 作用 | 层面 |
|---|---|---|
| `ForeignKey("labs.id")` | **外键约束**:数据库层面保证 lab_id 必须是 labs 表里真实存在的 id | 数据库 |
| `relationship()` | **对象级关联**:ORM 层面让你能 `equipment.lab` 直接拿到整个 Lab 对象 | Python |

区别:

```python
equipment.lab_id      # → 3(一个数字,只有 id)
equipment.lab         # → Lab 对象(lab.name、lab.location 都能点出来)
```

`relationship` 让 SQLAlchemy 帮你把"id 外键"升级成"对象引用",这是 ORM 最强大的特性之一。

---

## 第二章 关联查询:本课核心

### 2.1 需求:设备列表要显示实验室名字

```json
// 前端想要的返回:
{
  "id": 1, "name": "离心机",
  "lab_id": 3,
  "lab_name": "三楼生物实验室"    ← 这个名字在 labs 表里!
}
```

### 2.2 笨办法:N+1 问题(性能陷阱)

```python
# 最直觉的写法(千万别这么干):
for equipment in equipment_list:        # 假设 10 条设备
    lab_name = equipment.lab.name       # 每条都单独查一次 labs 表!
# 总共 1(查设备) + 10(逐条查实验室) = 11 次 SQL 查询
```

这就叫 **N+1 问题**:1 次查列表 + N 次查关联,数据一多数据库就被打爆。它是 ORM 面试和实战的超高频考点(你的后端路线文档"MySQL 清单"里就有"N+1 查询"这一条)。

### 2.3 正确做法:`joinedload` 一次查完

```python
query.options(joinedload(Equipment.lab))   # 关键:预加载关联
```

`joinedload` 的作用:让 SQLAlchemy 生成**一条带 JOIN 的 SQL**,设备和实验室一次查回来:

```sql
-- 大致等价于:
SELECT equipments.*, labs.*
FROM equipments
LEFT JOIN labs ON equipments.lab_id = labs.id
```

对比:

```
不用 joinedload:  11 次 SQL(1 + N)
用 joinedload:    1 次 SQL(JOIN 一次查完)
```

### 2.4 组装响应:_to_equipment_response

```python
def _to_equipment_response(equipment: Equipment) -> EquipmentResponse:
    """设备模型没有 lab_name 属性,需要从 lab 关联中补充实验室名称。"""
    result = EquipmentResponse.model_validate(equipment)
    result.lab_name = equipment.lab.name if equipment.lab else None
    return result
```

注意两件事:

1. **`model_validate` 不会自动带关联字段** —— EquipmentResponse 里的 `lab_name` 在 Equipment 模型上没有,所以要手动补
2. **`if equipment.lab else None`** —— 防御性写法:如果某设备没关联到实验室(脏数据),不至于整个接口崩掉

---

## 第三章 完整的 CRUD 业务逻辑(services/equipment_services.py)

### 3.1 分页查询(带筛选)

```python
def get_equipment_page_list(db, page, page_size, keywords=None, lab_id=None):
    query = db.query(Equipment)
    if keywords:
        query = query.filter(Equipment.name.ilike(f"%{keywords}%"))   # 模糊搜索
    if lab_id is not None:
        query = query.filter(Equipment.lab_id == lab_id)              # 按实验室筛选

    total = query.count()
    items = (query.options(joinedload(Equipment.lab))     # 防 N+1
             .order_by(Equipment.id.desc())
             .offset((page - 1) * page_size)              # 分页
             .limit(page_size)
             .all())
    return PageResponse(list=[...], total=total)
```

知识点:

- **`ilike`**:模糊匹配且不区分大小写(`%keywords%` 是 SQL 通配符,前后%表示"包含")
- **筛选条件用 if 叠加**:有 keywords 才加模糊条件,有 lab_id 才加筛选 —— 动态拼查询是 ORM 的常规操作
- **`PageResponse`**:本课在 common/response.py 新增的分页统一格式 `{list, total}`

### 3.2 新增/更新时的业务规则

```python
def _get_lab(db, lab_id):
    """新增或更新设备前,确认所属实验室存在。"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    return lab
```

**前置校验**:往设备里写 lab_id 之前,先确认这个实验室真的存在 —— 防止脏数据(外键约束是数据库兜底,业务校验是提前给出友好报错)。

```python
# 更新时的查重(有个精妙细节):
exist = db.query(Equipment).filter(
    Equipment.lab_id == target_lab_id,
    Equipment.name == target_name,
    Equipment.id != equipment_id,        # ← 排除自己!
).first()
```

`Equipment.id != equipment_id` 排除自身:否则"只改描述不改名字"也会被误判成重名。这是更新类接口查重的标准写法。

### 3.3 删除

```python
equipment = db.query(Equipment).filter(...).first()
if not equipment:
    raise BusinessException(message="设备不存在")
db.delete(equipment)
db.commit()
```

先查后删,不存在给业务异常 —— 幂等性上的明确选择。

---

## 第四章 接口层与权限分层(api/equipment.py)

```python
@router.get("/list")
def get_equipment_list(..., current_user: User = Depends(get_current_user), ...):
    # 查看:普通登录用户即可

@router.post("")
def create_equipment(..., current_user: User = Depends(get_current_admin), ...):
    # 新增:必须管理员
```

注意权限的分层设计:

| 操作 | 依赖 | 谁可以用 |
|---|---|---|
| 查看列表 | `get_current_user` | 所有登录用户 |
| 新增/修改/删除 | `get_current_admin` | 仅管理员 |

这就是 RBAC 的雏形:通过不同的依赖函数控制接口权限等级。

---

## 第五章 前端:API 层(api/equipment.js)

```javascript
export function getEquipmentPageList(params) {   // 分页+筛选
  return request({ url: '/api/equipment/list', method: 'get', params })
}
export function createEquipmentApi(data) {       // 新增
  return request({ url: '/api/equipment', method: 'post', data })
}
export function updateEquipmentApi(equipmentId, data) {  // 修改
  return request({ url: `/api/equipment/${equipmentId}`, method: 'put', data })
}
export function deleteEquipmentApi(equipmentId) {        // 删除
  return request({ url: `/api/equipment/${equipmentId}`, method: 'delete' })
}
```

注意路径参数的新写法(模板字符串):

```javascript
url: `/api/equipment/${equipmentId}`    // 反引号 + ${} 插值
// 实际发出: /api/equipment/3
```

对应后端的 `@router.put("/{equipment_id}")` 路径参数。

---

## 第六章 RESTful 路径设计回顾

到本课为止,后端的接口风格已经完全 RESTful 化了:

| 操作 | 方法 + 路径 | 说明 |
|---|---|---|
| 列表(分页) | `GET /api/equipment/list` | 查询参数在 URL(?page=1&keywords=xx) |
| 新增 | `POST /api/equipment` | 数据在 body |
| 修改 | `PUT /api/equipment/{id}` | id 在路径里 |
| 删除 | `DELETE /api/equipment/{id}` | id 在路径里 |

**资源用名词(equipment),动作用 HTTP 方法表达** —— 这就是 RESTful。

---

## 第七章 踩坑实录

| 坑 | 说明 |
|---|---|
| `lab_id` 写进设备但实验室不存在 | 需要 `_get_lab` 前置校验 |
| 更新时不改名也报"重名" | 查重时忘了 `id != 自己` |
| 列表里 lab_name 是 null | 忘了 joinedload 或忘了在 response 里补 lab_name |
| 每条数据都多一次 SQL | N+1 问题 → joinedload |

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| 外键(ForeignKey) | 数据库层面的关联约束,保证引用的 id 真实存在 |
| relationship | ORM 层面把外键升级成对象引用(equipment.lab) |
| 关联查询/JOIN | 一条 SQL 同时查多张表 |
| joinedload | SQLAlchemy 的预加载,用 JOIN 避免 N+1 |
| N+1 问题 | 查列表 1 次 + 每条各查 1 次关联 = 性能杀手 |
| ilike | 不区分大小写的模糊匹配 |
| PageResponse | 分页统一返回格式 {list, total} |
| RBAC | 基于角色的权限控制(get_current_user vs get_current_admin) |

---

## 本章自检清单

- [ ] 能画出 labs 和 equipments 的一对多关系图
- [ ] 能解释 ForeignKey 和 relationship 的区别(数据库层 vs 对象层)
- [ ] 能解释什么是 N+1 问题,joinedload 怎么解决它
- [ ] 能写出更新查重时"排除自身"的条件
- [ ] 能解释为什么列表接口用 get_current_user 而增删改用 get_current_admin
- [ ] 能说出 RESTful 四个操作分别用什么方法
- [ ] 前端会用模板字符串拼路径参数(`/api/equipment/${id}`)
