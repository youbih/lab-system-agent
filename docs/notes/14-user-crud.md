# 开发用户增删改功能

> 对应课程：第 14 节
> 对应项目：`agent-lab/lab-system-agent`
> 整理日期：2026-11-06
> 涉及文件：
> - 前端重点：`src/views/User.vue`
> - 前端接口与菜单：`src/api/user.js`、`src/layouts/Layout.vue`
> - 后端：`app/schemas/user.py`、`app/api/user.py`、`app/services/user_services.py`
> - 复用：管理员鉴权、密码哈希、统一响应与异常处理、用户列表加载
>
> 阅读建议：按小节阅读，配合源码理解每段代码的输入、执行顺序、返回结果与页面效果。

---

## 第零章 这节课干了什么

第 13 节已经能查询、搜索和分页展示用户，本节在列表上增加“新增、编辑、删除”操作，打通前后端的完整流程。

| 操作 | 页面动作 | 后端接口 |
|---|---|---|
| 新增 | 打开空表单，填写并确认 | `POST /api/user` |
| 编辑 | 把当前行回显到表单，修改并确认 | `PUT /api/user/{user_id}` |
| 删除 | 点击删除，确认后发送请求 | `DELETE /api/user/{user_id}` |

新增与编辑共用一个弹窗和保存函数，通过 `form.id` 判断当前模式。删除单独使用确认框。成功后都复用上一课的 `load()` 重新查询列表。

本文按整理时的实际源码讲解。实际接口测试、模拟接口检查和待完善事项分别记录，不把尚未进行的浏览器操作写成已经实测。

相关基础：[第 13 节用户列表](./13-user-list.md)、[第 12 节修改密码](./12-password-update.md)。本次只整理文档，没有再次创建或删除真实用户。

---

## 第一章 后端：请求模型决定能接收哪些数据

### 1.1 新增请求 UserCreateRequest

来自 `backend/app/schemas/user.py`，所用导入如下：

```python
from typing import Literal
from pydantic import BaseModel, Field, field_validator
```

Literal 来自 Python 标准库 typing，其他三个来自 Pydantic。它们不是数据库模型；当前文件另有 ConfigDict 用于响应模型，不能覆盖整个文件时误删。

```python
class UserCreateRequest(BaseModel):
    name: str| None =None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None 
    role: Literal["student", "admin"] = "student"
    status: Literal[0, 1] = 1
    username: str = Field(min_length=1, max_length=50)
    password:str="123"
    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value
```

**按执行顺序拆解：**

#### 第一步：声明账号与可选资料

```python
username: str = Field(min_length=1, max_length=50)
name: str | None = None
```

这两行是类字段节选。username 没有默认值，因此必填；长度限制与数据库账号列的 50 字符上限对应。name 等资料可以不传，后面 service 会提供名称兜底。请求模型只完成解析校验，还没有写数据库。

#### 第二步：限制新增时的角色与状态

```python
role: Literal["student", "admin"] = "student"
status: Literal[0, 1] = 1
```

role 只接受 student/admin，status 只接受 0/1，省略时分别使用学生和正常状态。Literal 是取值约束，不是管理员身份验证；能否调用新增接口仍由 get_current_admin 决定。

#### 第三步：在长度校验前去掉账号两端空白

```python
@field_validator("username", mode="before")
@classmethod
def strip_username(cls, value):
    if isinstance(value, str):
        return value.strip()
    return value
```

strip_username 是我们自己写的校验函数。before 表示在字段标准解析校验前处理输入；如果是字符串就去两端空白，然后把结果交回 Pydantic。比如 " ccc " 变成 "ccc"，后续查重也使用整理后的值；全空白会变空字符串，再被最小长度拒绝。非字符串原样交回，由字段规则继续校验。

#### 第四步：理解密码默认值

```python
password: str = "123"
```

这行按当前源码记录：API 调用时不传密码会使用默认值。页面另有必填和长度规则，因此从页面新增与直接 curl 的输入限制不完全相同。这里不是给已有用户改密码；创建前还必须通过 hash_password 生成哈希。

**把结果连起来：** JSON 先变成 UserCreateRequest；不符合已配置规则的输入返回 422，不进入创建业务。

### 1.2 编辑请求 UserUpdateRequest

```python
class UserUpdateRequest(BaseModel):
    name: str| None =None
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None 
    role:str | None=None
    status:int | None=None
```

**按执行顺序拆解：**

#### 第一步：允许只传需要更新的字段

```python
name: str | None = None
email: str | None = None
```

这些是字段节选。它们有默认 None，客户端只改名称时不必再发送全部资料。没有 username/password 字段，所以本接口不负责修改账号或密码。

#### 第二步：与 service 的排除规则配合

```python
payload = data.model_dump(exclude_none=True)
```

这句实际在 service 内，将模型转成字典并排除所有 None。未传字段和显式传入 null 都会被忽略，不能通过 email:null 清空邮箱；空字符串则不会被排除。

#### 第三步：区分已完成与尚未添加的规则

```python
role: str | None = None
status: int | None = None
```

当前更新模型仍使用普通 str/int，还没有同步新增模型的 Literal 取值限制。这是待完善项，不能在笔记里把未写的规则描述为已生效。

**把结果连起来：** 创建与更新的 schema 不同，更新不要求账号密码，并支持只改一部分资料。

---

## 第二章 后端 API：声明方法、路径和管理员依赖

### 2.1 新增用户接口

```python
@router.post("")
def create_user(
    data:UserCreateRequest,
    current_user:User=Depends(get_current_admin),
    db:Session=Depends(get_db),
):
    res=user_services.create_user(db,data)
    return Response.success(data=res)
```

**按执行顺序拆解：**

#### 第一步：匹配新增请求

```python
@router.post("")
```

路由前缀 /user 加总前缀 /api 后，空子路径就是 POST /api/user。POST 不会自动插入数据库，真正的插入还在下面的 service。

#### 第二步：取得请求数据和当前管理员

```python
data: UserCreateRequest
current_user: User = Depends(get_current_admin)
db: Session = Depends(get_db)
```

这是参数声明节选。data 来自 JSON，db 来自数据库会话依赖；管理员依赖会先检查身份和角色，学生不能调用新增。函数体没读取 current_user 也不意味着依赖不执行。

#### 第三步：调用服务并返回响应

```python
res = user_services.create_user(db, data)
return Response.success(data=res)
```

service 正常返回 UserResponse 后，外层 Response 包装 code/message/data。若 service raise，成功返回不会执行，错误交给全局异常处理器。

**把结果连起来：** 输入校验与管理员验证通过后才执行业务创建。

### 2.2 编辑用户接口

```python
@router.put("/{user_id}")
def update_user(
    user_id:int,
    data: UserUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = user_services.update_user(db,data,user_id)
    return Response.success(data=res)
```

**按执行顺序拆解：**

#### 第一步：从路径取得用户 ID

```python
@router.put("/{user_id}")
```

例如 PUT /api/user/4，路径参数 user_id 会被解析成整数 4；非数字 ID 返回 422。这里确定目标用户，与 token 所代表的当前管理员是两个概念。

#### 第二步：用更新模型解析请求体

```python
data: UserUpdateRequest
```

不再误用 UserCreateRequest，因此只提交名称也能更新，不要求附带 username/password。

#### 第三步：按服务函数签名传参

```python
res = user_services.update_user(db, data, user_id)
```

顺序必须与 def update_user(db,data,user_id) 一致。函数名也必须完全一致；createUser/create_user 或 updateUser/update_user 不会由 Python 自动互换。

**把结果连起来：** 路径决定改谁，请求体决定改什么，管理员依赖决定有没有权限。

### 2.3 删除用户接口

```python
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = user_services.delete_user(db, user_id, current_user)
    return Response.success()
```

**按执行顺序拆解：**

#### 第一步：使用 DELETE 方法

```python
@router.delete("/{user_id}")
```

不能与编辑一样注册成同路径同方法的 PUT。HTTP 方法与路径共同确定接口。

#### 第二步：不要求多余请求体

```python
res = user_services.delete_user(db, user_id, current_user)
```

删除只需要路径中的目标 ID，另由依赖提供当前管理员。service 要使用 current_user.id 防止删除自己，因此当前管理员仍需传入。

#### 第三步：正常结束返回成功

```python
return Response.success()
```

删除服务没有显式返回用户对象，成功时返回 data:null。这里的 res 目前没有继续使用，是可清理的冗余变量，不影响执行。

**把结果连起来：** 先确认管理员身份，再由服务检查和删除；没有额外 UserCreateRequest 请求体。

---

## 第三章 后端 Service：真正完成数据库操作

下面的三个函数是我们自己定义的，SQLAlchemy 的 query/add/commit 等是库提供的方法。业务层并不直接决定页面如何弹窗。

### 3.1 create_user：查重、哈希、创建和返回

```python
def create_user(db:Session,data:UserCreateRequest):
    """新增用户"""
    exist = db.query(User).filter(User.username==data.username).first()
    if exist:
        raise BusinessException(message="账号已存在")

    user=User(
        username=data.username,
        password=hash_password(data.password),
        name=data.name or data.username,
        role=data.role,
        email=data.email,
        phone=data.phone,
        avatar=data.avatar,
        status=data.status,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
```

**按执行顺序拆解：**

#### 第一步：按账号查重

```python
exist = db.query(User).filter(User.username == data.username).first()
if exist:
    raise BusinessException(message="账号已存在")
```

query 构建用户查询，filter 限定账号完全相同，first 执行后返回首条匹配 User 对象或 None。查重只需确认有没有，找到一条就够了；first 本身不保证数据库账号唯一。重复时 raise 中断后续创建。

#### 第二步：把请求数据转成 ORM 用户对象

```python
user = User(
    username=data.username,
    password=hash_password(data.password),
    name=data.name or data.username,
    role=data.role,
    email=data.email,
    phone=data.phone,
    avatar=data.avatar,
    status=data.status
)
```

User 是数据库模型，data 是请求模型。密码存 bcrypt 哈希，未填名称或空字符串时使用账号。例如只提供账号 test_user，最终 name 可以为 test_user，避免把 None 写到数据库非空列。构造对象时还没有完成持久化。

#### 第三步：加入会话并提交

```python
db.add(user)
db.commit()
```

add 把新对象放入会话；commit 提交事务，将记录保存到数据库。失败会抛异常，不应继续声称新增成功。

#### 第四步：刷新并构造用户响应

```python
db.refresh(user)
return UserResponse.model_validate(user)
```

refresh 重新读取数据库中的对象字段；model_validate 根据 UserResponse 提取允许返回的字段。密码不属于响应字段。最终 API 再包外层 Response，浏览器通过 res.data 取得用户资料。

**把结果连起来：** 请求账号 → 查重 → 明文转哈希 → 构造 User → 提交 → 返回安全的用户资料结构。

### 3.2 update_user：只更新请求中值不为 None 的字段

```python
def update_user(db: Session, data: UserUpdateRequest, user_id: int):
    """更新用户"""
    user = db.query(User).filter(User.id ==user_id).first()
    if not user:
        raise BusinessException(message="用户不存在")
    payload=data.model_dump(exclude_none=True)
    for filed,value in payload.items():
        setattr(user,filed,value)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
```

**按执行顺序拆解：**

#### 第一步：找到要编辑的用户

```python
user = db.query(User).filter(User.id == user_id).first()
if not user:
    raise BusinessException(message="用户不存在")
```

user_id 来自 URL。查不到时立即返回业务异常，不对其他用户尝试修改，也不创建替代用户。

#### 第二步：生成更新字典

```python
payload = data.model_dump(exclude_none=True)
```

比如请求 {name:"新名字",email:null}，payload 中只剩 name；空对象则得到空字典。它排除的是 None，不是“所有空值”，所以空字符串和 0 仍能进入更新。

#### 第三步：按字段名写入对象

```python
for filed, value in payload.items():
    setattr(user, filed, value)
```

这段保留当前源码的变量名 filed，两处一致所以可运行。它表示字段名，通常拼成 field。假设一轮得到 ("name","新名字")，setattr 就相当于 user.name="新名字"，下一轮处理另一字段。

#### 第四步：提交并返回最新资料

```python
db.commit()
db.refresh(user)
return UserResponse.model_validate(user)
```

赋值先改变会话里的 ORM 对象，commit 才持久化；refresh 是重新读取，不是让 commit 生效。返回响应模型后，前端能看到保存后的资料。

**把结果连起来：** 查找 → 提取非 None 字段 → 循环赋值 → 提交刷新 → 返回；账号和密码不在当前更新模型中。

### 3.3 delete_user：先拦截删除自己，再检查目标是否存在

```python
def delete_user(db: Session,user_id:int,current_user:User):
    """删除用户"""
    if user_id==current_user.id:
        raise BusinessException(message="不能删除当前登录的账号")
    user=db.query(User).filter(User.id == user_id).first()
    if not user:
        raise BusinessException(message="用户不存在")
    db.delete(user)
    db.commit()
```

**按执行顺序拆解：**

#### 第一步：保护当前登录账号

```python
if user_id == current_user.id:
    raise BusinessException(message="不能删除当前登录的账号")
```

左边是目标 ID，右边是发起请求的管理员 ID。相同时提前中断，不执行删除。这个判断只保护删除自己，并不自动保护管理员被修改角色或状态等其他操作。

#### 第二步：查询目标，不存在就拒绝

```python
user = db.query(User).filter(User.id == user_id).first()
if not user:
    raise BusinessException(message="用户不存在")
```

找不到返回 None。重复删除同一个已删除 ID，第二次会进入这条分支。

#### 第三步：标记删除并提交事务

```python
db.delete(user)
db.commit()
```

delete 将该 ORM 对象标记为删除，commit 执行并提交。本课是从用户表删除记录，不是只把 status 改成 0。当前没有复杂关联业务的删除策略。

**把结果连起来：** 只有权限通过、目标不是自己且确实存在，才会提交删除。

### 3.4 HTTP 状态码和业务码不要混淆

当前 BusinessException 默认业务 code 为 500，而业务异常处理器使用 HTTP 200 返回。因此“账号已存在”“用户不存在”“不能删除当前登录的账号”可能是 HTTP 200 + JSON code:500，这是当前主动业务分支，不必然是程序崩溃。未预期异常则可能是真正 HTTP 500，需要查看日志。密码错误、无权限等分支有各自显式业务码。

---

## 第四章 前端 API：每种操作封装一个函数

### 4.1 新增请求 createUserApi

```javascript
export function createUserApi(data) {
  return request({
    url: '/api/user',
    method: 'post',
    data
  })
}
```

**按执行顺序拆解：**

#### 第一步：接收整个表单对象

```javascript
export function createUserApi(data) {
```

createUserApi 是项目定义并导出的函数，形参 data 接收 User.vue 传来的 form。它不负责打开弹窗，也不直接操作数据库。

#### 第二步：用 POST 请求体发送

```javascript
return request({ url: "/api/user", method: "post", data })
```

data 简写等于 data:data。公共 Axios 实例负责附加 token 和处理响应。return 交回 Promise，页面才能 await 后检查业务码。

### 4.2 更新请求 updateUserApi

```javascript
export function updateUserApi(userId, data) {
  return request({
    url: `/api/user/${userId}`,
    method: 'put',
    data
  })
}
```

**按执行顺序拆解：**

#### 第一步：区分路径 ID 和请求体

```javascript
export function updateUserApi(userId, data) {
```

例如第一个参数为 4，第二个为编辑表单。两个参数不能互换，否则 URL 或请求体会错误。

#### 第二步：构造路径并发送 PUT

```javascript
url: `/api/user/${userId}`,
method: "put",
data
```

这是配置属性节选。模板字符串将 ID 拼成路径；data 是要修改的字段。当前 UserUpdateRequest 没有 username/password，表单多传这些键不会自动让后端支持修改它们。

### 4.3 删除请求 deleteUserApi

```javascript
export function deleteUserApi(userId) {
  return request({
    url: `/api/user/${userId}`,
    method: 'delete'
  })
}
```

**按执行顺序拆解：**

#### 第一步：只需要目标 ID

```javascript
export function deleteUserApi(userId) {
```

传入的是数值 ID，不是整行对象。页面先取得 row.id，再调用这个函数。

#### 第二步：发送无请求体的 DELETE

```javascript
return request({ url: `/api/user/${userId}`, method: "delete" })
```

当前后端删除接口没有请求体，所以不需要 data。早期误写 data 但没有定义变量，会在浏览器构建请求配置时就报 ReferenceError，后端根本收不到请求。

---

## 第五章 User.vue：新增和编辑共用一个弹窗

### 5.1 本课新增的状态与导入

```javascript
import { getUserPageList, createUserApi, updateUserApi, deleteUserApi } from '@/api/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ref, reactive } from 'vue'
```

这里合并展示本课使用的主要导入，省略了列表生命周期和图标相关导入，不是整个 import 区的替代品。API 函数来自项目，消息组件来自 Element Plus，响应式工具来自 Vue。

```javascript
const formRef = ref()
const dialogVisible = ref(false)
const formLoading = ref(false)
const form = reactive({
  username: '',
  name: '',
  role: 'student',
  email: '',
  phone: '',
  avatar: '',
  status: 1,
  password: ''
})
```

**按执行顺序拆解：**

#### 第一步：保存表单实例和弹窗状态

```javascript
const formRef = ref()
const dialogVisible = ref(false)
```

formRef 在表单挂载后引用 el-form 实例，用于 validate；dialogVisible 控制弹窗显示。它们都不是正在编辑的用户资料。

#### 第二步：保存按钮提交状态

```javascript
const formLoading = ref(false)
```

确认按钮绑定 :loading="formLoading"。它与列表的 loading 独立；变量名要统一，fromLoading 与 formLoading 不是一个名称。

#### 第三步：保存正在编辑的字段

```javascript
const form = reactive({ username: "", name: "", role: "student", email: "", phone: "", avatar: "", status: 1, password: "" })
```

form 是响应式对象，输入框通过 v-model 同步字段。当前初始对象没有 id，resetForm 随后会添加 id:null；Vue 3 的 reactive 支持这个新增属性，不应误判为不能响应。

**把结果连起来：** form 存资料，formRef 存组件实例，dialogVisible 控制显示，formLoading 控制提交状态。

### 5.2 弹窗标题、账号禁用、密码显隐与取消

```vue
<el-dialog v-model="dialogVisible" :title="form.id ? '编辑' : '新增'" width="450">
  <el-form ref="formRef" :model="form" :rules="rules">
    <el-form-item label="账号" prop="username">
      <el-input :disabled="!!form.id" v-model="form.username" />
    </el-form-item>
    <el-form-item v-if="!form.id" label="密码" prop="password">
      <el-input type="password" show-password v-model="form.password" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="dialogVisible = false">取消</el-button>
    <el-button type="primary" :loading="formLoading" @click="handleSave">确认</el-button>
  </template>
</el-dialog>
```

这是保留关键绑定的结构节选，实际弹窗还包含名称、角色、邮箱、手机号和状态字段。

**按执行顺序拆解：**

#### 第一步：用 v-model 同步弹窗开关

```vue
v-model="dialogVisible"
```

这里是 Vue 模板属性节选。dialogVisible 为 true 就显示，为 false 就关闭。组件关闭操作也会更新绑定状态。模板自动解包 ref，所以 @click 内不用写 .value；JavaScript 函数里要写。

#### 第二步：用 ID 判断模式

```vue
:title="form.id ? '编辑' : '新增'"
:disabled="!!form.id"
```

这两个属性在不同标签上。新增时 id 为 null，标题是新增，账号可输入；编辑时 id 为正整数，标题是编辑，账号禁用。!! 将值转成布尔值。后端也没有把账号放进更新模型。

#### 第三步：只在新增时挂载密码表单项

```vue
<el-form-item v-if="!form.id" label="密码" prop="password">
```

这是标签起始片段。新增需要密码；编辑当前只改资料，不修改密码。用 v-if 移除整个表单项后，编辑时不会再被该项的必填规则阻止。v-show 只是隐藏显示，不能直接当成移除表单校验的同义替代。

#### 第四步：按钮关闭或提交

```vue
@click="dialogVisible = false"
@click="handleSave"
```

取消关闭表单弹窗，不调用保存接口；确认则由 handleSave 校验后提交。这里的取消与删除确认框的 cancel 是两种不同组件交互。

**把结果连起来：** 同一份表单由 id 控制行为；隐藏密码避免“编辑要求输入、实际后端又不更新”的误导。

### 5.3 表单校验规则

```javascript
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 3, max: 10, message: '密码是3到10位', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式错误', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式错误', trigger: 'blur' }]
}
```

**按执行顺序拆解：**

#### 第一步：必填项按 prop 关联

```javascript
username: [{ required: true, message: "请输入账号", trigger: "blur" }]
```

这是规则对象中的字段节选。el-form-item 的 prop=username 与 rules.username、form.username 对应；如果 prop 拼成 prob，规则就无法正确关联。

#### 第二步：密码规则只约束新增页面交互

```javascript
password: [
  { required: true, message: "请输入密码", trigger: "blur" },
  { min: 3, max: 10, message: "密码是3到10位", trigger: "blur" }
]
```

前端新增要求 3～10 位，编辑时密码表单项被移除。这个前端限制并没有自动变成后端密码长度规则，所以此前 curl 使用较长测试密码成功，与页面不允许超过 10 位并不矛盾。

#### 第三步：格式检查与提交前校验

邮箱使用 email 规则，手机号使用正则；trigger=blur 是失去焦点触发。点击确认时仍会调用 formRef.value.validate 做整体检查。前端检查改善交互，后端规则仍需独立定义。

---

## 第六章 User.vue：打开新增与编辑表单

### 6.1 resetForm：清空上一次的资料和密码

```javascript
const resetForm = () => {
  Object.assign(form, {
    id: null,
    username: '',
    name: '',
    role: 'student',
    email: '',
    phone: '',
    avatar: '',
    status: 1,
    password: ''
  })
}
```

**按执行顺序拆解：**

#### 第一步：保留响应式对象，批量恢复默认值

```javascript
Object.assign(form, { id: null, username: "", name: "", role: "student", email: "", phone: "", avatar: "", status: 1, password: "" })
```

Object.assign 写入现有对象，不是重新给 const form 赋值。绑定原对象的输入框会更新。id:null 特别重要，否则上一次编辑 ID 残留，下一次新增可能误走更新分支。

#### 第二步：显式重置密码

```javascript
password: ""
```

这是重置对象中的字段。v-model 会保存输入内容，如果重置时漏掉 password，再次新增可能带着上次密码；因此初始化与重置两处都要包含它。

**把结果连起来：** resetForm 清资料和模式，但当前没有清除 Element Plus 组件内部的校验提示，见待完善事项。

### 6.2 handleCreate：先重置，再打开

```javascript
const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}
```

**按执行顺序拆解：**

#### 第一步：回到新增初始状态

```javascript
resetForm()
```

调用我们自己写的 resetForm，清掉旧 ID、旧资料和密码。此时不向后端新增用户。

#### 第二步：显示弹窗

```javascript
dialogVisible.value = true
```

JavaScript 中对 ref 写 .value。页面根据 null ID 显示新增标题、可编辑账号和密码框；真正创建要等用户点确认。

### 6.3 handleEdit：用当前行数据回显

```javascript
const handleEdit = (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    username: row.username,
    name: row.name,
    role: row.role,
    email: row.email,
    phone: row.phone,
    avatar: row.avatar,
    status: row.status
  })
  dialogVisible.value = true
}
```

**按执行顺序拆解：**

#### 第一步：从表格行接收资料并清旧数据

```javascript
const handleEdit = (row) => {
  resetForm()
```

row 是表格插槽传入的当前用户对象，不是只有 ID。先重置使上次编辑的密码/其他数据不残留。

#### 第二步：将用户 ID 与可显示字段填入表单

```javascript
Object.assign(form, { id: row.id, username: row.username, name: row.name, role: row.role, email: row.email, phone: row.phone, avatar: row.avatar, status: row.status })
```

例如 row.id 为 3，表单就进入编辑模式；名称和联系方式回显已有值。这里从列表读取现有快照，没有额外请求详情接口；密码既没有返回也不应回显。

#### 第三步：显示编辑弹窗

```javascript
dialogVisible.value = true
```

由于 form.id 已有值，标题变编辑，账号禁用，密码项不挂载；表单中其他 v-model 字段可以修改。

**把结果连起来：** 点击当前行编辑 → 清旧表单 → 复制这一行 → 打开编辑模式。

---

## 第七章 User.vue：handleSave 统一保存新增和编辑

```javascript
const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  formLoading.value = true
  try {
    const res = form.id ? await updateUserApi(form.id, form) : await createUserApi(form)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success('操作成功')
      load()
    }
  } finally {
    formLoading.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：校验，不通过就不发请求

```javascript
const valid = await formRef.value.validate().catch(() => false)
if (!valid) return
```

validate 是 Element Plus 表单实例的方法。成功得到通过结果；校验拒绝由 catch 转为 false，再提前结束。这里的 catch 只处理这次表单校验 Promise，不是整个函数所有异常。

#### 第二步：显示提交状态

```javascript
formLoading.value = true
```

确认按钮开始显示加载。此处不要写成 fromLoading 或未声明变量；这也是之前点击确认报错的原因之一。

#### 第三步：根据 ID 选择不同请求

```javascript
const res = form.id ? await updateUserApi(form.id, form) : await createUserApi(form)
```

这是三元表达式。有 ID 就更新指定用户，没有 ID 就创建。只会选择其中一个分支，不会同时发两个请求。await 等待所选 Promise；公共拦截器返回业务 JSON，所以后面读 res.code。

#### 第四步：成功后关闭、提示并重新查询

```javascript
if (res.code === 200) {
  dialogVisible.value = false
  ElMessage.success("操作成功")
  load()
}
```

必须同时写对 .value 和 false：直接 dialogVisible=true 是给 const 重新赋值；设为 true 又不能关闭。load 是上一课自己的列表加载函数，重新从后端取最新列表。业务失败不进入成功分支。

#### 第五步：最后结束按钮加载

```javascript
finally {
  formLoading.value = false
}
```

即使请求抛异常也会结束加载。finally 不代替 catch；当前请求错误提示主要由公共 request.js 负责。由于这里没有 await load()，提交结束与列表重新加载结束是两个时刻。

**把结果连起来：** 点确认 → 前端校验 → 根据 ID 发 POST/PUT → 成功关闭与刷新 → 恢复提交状态。

---

## 第八章 User.vue：删除确认、then 与 catch

### 8.1 表格把整行传给事件处理函数

```vue
<el-table-column prop="status" label="操作" width="160" align="center">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px">
              <el-button type="primary" text style="margin: 0" @click="handleEdit(row)"
                >编辑</el-button
              >
              <el-button type="danger" text style="margin: 0" @click="handleDelete(row)"
                >删除</el-button
              >
            </div>
          </template>
        </el-table-column>
```

**按执行顺序拆解：**

#### 第一步：从插槽取得当前行

```vue
<template #default="{ row }">
```

这是模板起始片段。row 是这一行用户对象，因此编辑和删除都可以使用它的 id、username 等字段。不要把该函数参数命名为 userId 后却在内部读取未定义的 row。

#### 第二步：点击时调用对应函数

```vue
@click="handleEdit(row)"
@click="handleDelete(row)"
```

点击编辑传行对象给 handleEdit；点击删除传行对象给 handleDelete。API 函数再接收 row.id，不是直接把整个对象拼进 URL。

#### 第三步：只控制布局的样式

```vue
align="center"
style="display: flex; align-items: center; justify-content: center; gap: 8px"
```

这是列属性与内部容器样式节选。居中和 8px 间距只改变布局，按钮 margin:0 避免默认外边距叠加；不改变请求逻辑。操作列沿用了 prop=status，但实际显示由插槽决定，不需要依赖该 prop。

### 8.2 handleDelete：只有确认后才发送 DELETE

```javascript
const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除用户[${row.username}]?`, '确认删除', { type: 'warning' })
    .then(async () => {
      const res = await deleteUserApi(row.id)
      if (res.code === 200) {
        ElMessage.success('删除用户成功')
        load()
      }
    })
    .catch((error) => {
      if (error !== 'cancel' && error !== 'close') {
        console.error('删除失败', error)
      }
    })
}
```

**按执行顺序拆解：**

#### 第一步：接收行对象并显示确认框

```javascript
ElMessageBox.confirm(`确认删除用户[${row.username}]?`, "确认删除", { type: "warning" })
```

ElMessageBox 来自 Element Plus，confirm 返回 Promise。模板字符串把账号放进提示，让用户知道即将删谁。到这里还没有调用删除接口。

#### 第二步：确认后进入 then 发请求

```javascript
.then(async () => {
  const res = await deleteUserApi(row.id)
```

这是 Promise 链节选。用户确认时 Promise 完成，then 的异步回调才执行。row.id 是真正的目标 ID，await 等后端删除结果。取消或关闭不会执行这条正常分支。

#### 第三步：业务成功才提示和刷新

```javascript
if (res.code === 200) {
  ElMessage.success("删除用户成功")
  load()
}
```

后端拒绝删除自己等情况不会提示成功。重新查询列表后，删除记录不再出现；当前不是前端自己先从数组中 splice 掉一行。

#### 第四步：明确处理取消和异常

```javascript
.catch((error) => {
  if (error !== "cancel" && error !== "close") {
    console.error("删除失败", error)
  }
})
```

confirm 将取消/关闭作为 Promise 拒绝来报告，catch 识别后安静结束。删除请求抛异常也会进入此 catch，并记录错误；通常公共请求层已显示提示。不是加了 catch 才能防止取消删除，原本取消就不会走 then。

**把结果连起来：** 问是否删除 → 确认才请求；取消直接结束；成功刷新；请求抛错交给 catch。

### 8.3 catch 到底捕获什么

把确认框理解成一次提问：确认走 then；取消/关闭走 catch。catch 的意义是“我知道用户可能不确认，并安排了正常结束方式”，避免未处理的 Promise 拒绝。

还要区分两种失败：

- Promise 被拒绝或回调抛异常：进入链上的 catch。
- HTTP 200 返回非 200 的业务 code：如果公共拦截器仍正常返回 JSON，它不会自动进入 catch，需要依靠 res.code 判断。

当前 load() 没有 await 或 return，所以列表刷新发生的异步错误不会自动接到这条删除 Promise 链上。这是后续完善点，不应把“加了 catch”理解为所有异步错误都已经捕获。

---

## 第九章 完整流程对照

```text
新增：
点击新增 → resetForm → 显示弹窗 → 用户填写 → handleSave 校验
    → form.id 为空 → POST /api/user → 查重/哈希/提交
    → 响应成功 → 关闭弹窗 → load 更新列表

编辑：
点击编辑(row) → resetForm → 回显 row → 有 ID、隐藏密码
    → handleSave 校验 → PUT /api/user/{id} → 查找/赋值/提交
    → 响应成功 → 关闭弹窗 → load 更新列表

删除：
点击删除(row) → 确认框
    ├─ 取消/关闭 → catch 结束，不发 DELETE
    └─ 确认 → DELETE /api/user/{id} → 检查不是自己/目标存在/提交删除
        → 响应成功 → 提示 → load 更新列表
```

### 9.1 管理员菜单展示

`Layout.vue` 的用户管理菜单也增加了角色判断：

```vue
<el-menu-item index="/manager/user" v-if="userInfo?.role === 'admin'">
  <el-icon><User /></el-icon>
  <span>用户管理</span>
</el-menu-item>
```

这里读取前端共享的用户信息；只有 role 为 admin 时才渲染菜单项，普通学生不会看到该入口。`?.` 避免用户信息为空时报属性读取错误。

隐藏菜单用于界面展示，不代替服务器鉴权。直接输入网址或用 curl 调用接口时，真正的管理员限制仍由后端 `get_current_admin` 执行。

---

## 第十章 本课验证记录与复现指令

### 10.1 用户手动 curl 的已确认结果

| 场景 | 对话中实际结果 |
|---|---|
| 新增 curl_test_01 | 成功，返回 ID 4 |
| 重复新增同账号 | 返回“账号已存在” |
| 缺少 username | 返回 422 |
| 修改名称与手机号 | 成功，其他未改字段保留 |
| 空对象更新 | 成功，资料保持原值 |
| email:null 更新 | 邮箱未清空，符合 exclude_none 行为 |
| 更新不存在的 ID | 返回“用户不存在” |

这张表记录此前操作，不表示本文生成时重新创建这些用户。

### 10.2 剩余真实 HTTP 检查结果

用户先禁用测试账号后，授权助手接着测试。2026-11-06 的本机后端 HTTP 检查共 21 项，均通过；下面保留不含 token/密码的结果摘要。

| 场景 | HTTP / 业务码 | 结果 |
|---|---|---|
| 管理员登录（测试准备） | 200 / 200 | 通过 |
| 禁用账号无法登录 | 200 / 403 | 通过 |
| 管理员恢复测试账号 | 200 / 200 | 通过 |
| 恢复后学生登录成功 | 200 / 200 | 通过 |
| 非数字用户ID被拒绝 | 422 / 422 | 通过 |
| 学生不能查询管理员列表 | 200 / 403 | 通过 |
| 学生不能新增 | 200 / 403 | 通过 |
| 学生不能修改 | 200 / 403 | 通过 |
| 学生不能删除 | 200 / 403 | 通过 |
| 未携带token不能新增 | 401 / 401 | 通过 |
| 未携带token不能修改 | 401 / 401 | 通过 |
| 未携带token不能删除 | 401 / 401 | 通过 |
| 无效token不能新增 | 401 / 401 | 通过 |
| 无效token不能修改 | 401 / 401 | 通过 |
| 无效token不能删除 | 401 / 401 | 通过 |
| 管理员不能删除当前登录账号 | 200 / 500 | 通过 |
| 删除不存在的用户 | 200 / 500 | 通过 |
| 管理员删除测试用户 | 200 / 200 | 通过 |
| 删除后查询为空，其他用户资料与基线一致 | 查询与基线核对 | 通过 |
| 再次删除同一用户 | 200 / 500 | 通过 |
| 删除用户后原学生token失效 | 401 / 401 | 通过 |

测试最终删除了 curl_test_01（ID 4），其余 3 个原有用户资料与基线一致。新增的拒绝请求没有意外创建用户。删除后旧 token 被拒绝是因为依赖查库找不到用户；当前消息统一为“用户被禁用”，不意味着给这个 JWT 建立了单独的撤销记录。

### 10.3 当前前端检查的证据边界

本次整理时使用模拟接口检查了新增/编辑模式、密码重置、校验失败不发请求、保存后关闭、删除确认/取消/关闭/请求异常，均通过。这些模拟检查没有发送真实 HTTP，也没有修改 MySQL。

使用本机已安装的 Node 24.16.0 执行前端 Vite 生产构建，构建成功。存在资源块大于 500 kB 的体积提示，不影响本次构建完成；这项检查不验证真实浏览器的布局与点击行为。

浏览器中实际点选、校验提示清理、多页最后一行删除等交互仍应按具体操作验证；构建或模拟成功不等于浏览器全部场景实测通过。

### 10.4 curl 复现模板

新开终端后，之前设置的 BASE_URL、ADMIN_TOKEN 等变量不一定还在，需要重新设置。后端未加载接口时先查看 /docs；HTTP 404 与业务用户不存在不是同一件事。下面使用占位值，写操作只针对自己创建的测试账号。

```bash
BASE_URL='http://localhost:8000'
ADMIN_TOKEN='替换为管理员登录返回的token'

curl -sS -i -X POST "$BASE_URL/api/user" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"username":"lesson14_demo","password":"TestPass","name":"测试用户","role":"student","status":1}'

# 将值换成新增响应中的 data.id，不能盲目沿用历史 ID 4。
TEST_USER_ID=替换为新建测试用户的数字ID

curl -sS -i -X PUT "$BASE_URL/api/user/$TEST_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"修改后的测试用户"}'

# 删除放在其他测试之后；这条会真实删除该测试用户。
curl -sS -i -X DELETE "$BASE_URL/api/user/$TEST_USER_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

-i 让 curl 同时显示 HTTP 响应头与业务 JSON。BASE_URL/ADMIN_TOKEN 是当前 shell 变量，切换 Conda 环境通常不影响 curl 的 HTTP 方法与路由匹配；新开终端则需要重新设置这些变量。

---

## 第十一章 本课踩坑实录

| 问题 | 原因 | 当前处理 |
|---|---|---|
| 新增/更新报没有对应属性 | API 使用 create_user/update_user，service 却用 createUser/updateUser | 统一 snake_case 名称 |
| createu_ser | 改名时下划线位置拼错 | 改为 create_user |
| 新增时 name 为 None 导致非空列错误 | schema 可省略名称，数据库 name 非空 | service 用 data.name or data.username |
| 删除接口误注册 PUT | 与编辑相同方法/路径，不能表达 DELETE 操作 | 改成 DELETE，移除多余请求体 |
| 新接口 curl 返回 404 | 旧服务没有加载最新路由 | 重启、查看 /docs 的实际接口清单 |
| email=data.email,u | 多打字符导致 Python 语法错误，服务无法启动 | 删除多余 u，语法检查通过 |
| formLoading 未定义 | 定义/模板用了 fromLoading，函数里用了 formLoading | 统一名称 |
| createUserApi/updateUserApi/ElMessage 未定义 | 页面缺少导入 | 补齐 import |
| 保存后弹窗没关或赋值报错 | 写 dialogVisible=true，漏 .value 且布尔值方向错 | 改为 dialogVisible.value=false |
| show-passwprd / prob | 属性拼写错误 | 改为 show-password / prop |
| 重开新增弹窗残留密码 | 初始化、重置都没包含 password | 两处都补 password 空字符串 |
| 取消表单按钮没反应 | 没绑定事件 | 点击设 dialogVisible=false |
| 删除请求 data 未定义 | API 函数只接 userId，却在配置中引用 data | 删除无用 data |
| 点击删除报 row 未定义 | 函数参数叫 userId，内部却用 row | 统一接收 row |
| 取消删除出现 Promise 拒绝提示 | confirm 对取消返回拒绝，未处理 | 增加 catch，区分取消/关闭与异常 |
| 编辑必须填密码但密码不更新 | 共用表单项要求必填，后端更新模型又没有 password | 密码项只在新增时 v-if 显示 |

---

## 第十二章 本节复查结论

前述函数命名、导入、弹窗关闭、密码重置、编辑密码显隐、取消删除和删除请求问题均已处理。当前新增、编辑、删除主流程已完成本节课程范围内的开发与检查。

项目整体框架仍在跟随课程搭建，尚未完成全部功能。根据学习安排，参数校验和异步刷新等进一步完善事项只作记录，不作为现在继续跟课或提交本节代码的前置要求；统一列在本文最后的“课程结束后统一完善”。

---

## 常见问题

**Q1：POST、GET、PUT、DELETE 有什么区别？**

本项目用 GET 查列表，POST 新增，PUT 更新，DELETE 删除。方法表达接口语义，真正是否改数据库取决于函数代码。POST 请求体不是自动加密，传输是否加密取决于 HTTPS 等配置。

**Q2：v-model 会自动保存数据库吗？**

不会。它只同步输入框与前端变量；例如输入名称改变 form.name，仍要点确认并调用 API，后端提交后才保存。

**Q3：first 是把同账号的第一条拿出来吗？**

是，返回首条匹配 ORM 对象，找不到返回 None。查重只关心是否存在，所以一条就够；数据唯一性还要按数据库约束等设计保证。

**Q4：更新时为什么还需要 UserResponse？**

数据库中的 user 是 ORM 对象，UserResponse 限定对外返回的字段并校验结构。它不是另建一张用户表，也不会自动把所有数据库字段都输出。

**Q5：为什么取消不删除，还要补 catch？**

取消本来就不会进 then，补 catch 是明确处理 Promise 的拒绝，让正常取消安静结束，同时处理链内的真实异常。

**Q6：为什么编辑时不直接改密码？**

当前更新模型不接受 password，用户也不应看到数据库哈希。密码修改走已有专用功能；如果以后需要管理员重置别人密码，应单独设计接口与权限。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| CRUD | 创建、读取、更新、删除四类数据操作 |
| 路径参数 | URL 中的目标标识，如 /api/user/4 的 4 |
| 请求体 | 本课 POST/PUT 中提交的 JSON 数据 |
| Literal | Python 类型声明中的允许取值集合，可供 Pydantic 校验 |
| field_validator | Pydantic 字段校验/转换入口 |
| Object.assign | 把属性批量赋到现有对象，Vue 表单中可用于重置和回显 |
| v-model | Vue 的组件/输入与状态双向绑定 |
| v-if | 条件成立才创建相应模板节点或组件 |
| Promise | 表示异步操作未来完成或拒绝的对象 |
| then | 安排 Promise 完成后的处理 |
| catch | 处理此前链上的拒绝与异常 |
| finally | 安排正常或异常完成后的收尾，不自动吞掉异常 |
| ref.value | 在 JavaScript 中读写 Vue ref 的值 |
| 业务码 | JSON 中的 code，与 HTTP 状态码分别判断 |

---

## 本章自检清单

- [ ] 能说清新增、编辑、删除对应的方法和路径
- [ ] 能解释请求 schema 与数据库 User 模型的区别
- [ ] 能解释 username 的 trim、长度校验和查重顺序
- [ ] 能说出新增角色/状态有哪些合法值，以及更新约束尚未同步
- [ ] 能解释 first 返回对象或 None，不保证唯一性
- [ ] 能解释 hash_password、add、commit、refresh 的不同作用
- [ ] 能把 model_dump、字典循环、setattr 和 UserResponse 串起来
- [ ] 能解释 form.id 如何控制新增/编辑模式
- [ ] 能解释为什么初始表单和 resetForm 都要清密码
- [ ] 知道模板可自动解包 ref，脚本写值要用 .value
- [ ] 能解释编辑时为什么用 v-if 移除密码表单项
- [ ] 能口述 handleSave 从校验到请求、关闭、刷新、收尾的过程
- [ ] 能解释删除时 row 与 row.id 分别传给哪一层
- [ ] 能说清确认、取消、关闭、请求失败分别如何流转
- [ ] 知道非成功业务码不一定让 Promise reject
- [ ] 知道真实测试账号 ID 4 已被清理，不能盲目复用旧 ID
- [ ] 能区分当前源码检查、模拟接口验证、真实 HTTP 和浏览器实际操作

---

## 附录：课程结束后统一完善

**处理时间：跟随博主完成全部课程、整体框架搭建结束之后，再统一评估和修改。** 当前只保留问题、位置与思路，不改动相应代码，也不因这些记录把本节已完成的课程内容视为未完成。

优先保留的两项：

1. `backend/app/schemas/user.py` 第 24、25 行：更新请求的角色、状态取值约束。
2. `frontend/src/views/User.vue` 第 224、252 行：保存或删除后调用 `load()` 的等待与异常处理方式。

下面一并保存其他课堂中发现的后续完善点。行号对应 2026-11-06 的源码，未来修改前需重新定位。

| 位置 | 尚需完善 | 影响与建议 |
|---|---|---|
| backend/app/schemas/user.py 第 24、25 行 | 更新 role/status 仍为普通 str/int | 新增已用 Literal，更新仍可接收其他值；后续同步取值约束 |
| frontend/src/views/User.vue 第 176 行 | resetForm 只重置数据，没有 clearValidate | 取消有错误的表单再重开，可能残留校验提示；可在 DOM 更新后清理组件校验状态 |
| frontend/src/views/User.vue 第 224、252 行 | 调用 load() 没有 await/return | 保存/删除成功后刷新失败，不会自动被当前异步链捕获；可明确等待并单独区分刷新错误与保存错误 |
| frontend/src/views/User.vue 第 207、208 行；backend/app/schemas/user.py 第 42 行 | 前端密码 3～10 位，后端尚无同等长度约束且有默认值 | 页面与 curl 输入策略不同；后续按统一业务要求调整 |
| frontend/src/views/User.vue 第 131、132 行 | Loading/ElPopover 等导入未使用 | 可清理，不影响当前功能 |

更新模型兼用于个人资料接口所带来的角色修改权限问题，已按用户安排留待后续处理；本节不重复测试该路径，也没有擅自修改相关代码。

操作列的 prop=status 与展示无直接关系，可后续移除以表达更清楚；它不是当前删除功能失败的原因。最后一页只剩一条数据时删除后的分页回退，也建议补充浏览器验证，不能只凭源码假定已出错或已全部通过。
