# 智能实验室预约系统 · 全栈学习项目

[中文](./README.md) | [English](./README.en.md)

跟随课程逐步开发的前后端分离项目，目标是构建实验室预约系统。目前完成到**第 18 节：开发实验室预约功能**，已实现账户与个人中心、管理员用户/实验室/设备管理、学生端实验室与设备浏览，以及提交待审核预约。

这是课程学习中的阶段版本，整体框架仍在跟随课程搭建。下一节开发“我的预约和预约审核”；项目目前没有接入 AI/Agent 功能。进一步的校验、数据库约束和其他完善事项记录在课程笔记末尾，待全部课程结束后统一处理。

## 已有功能与课程进度

| 功能 | 当前状态 |
|---|---|
| 用户注册、登录 | 已有实现；注册用户默认为学生 |
| JWT 身份验证 | 后端检查 token 和用户状态，前端保存 token 并随请求携带 |
| 统一响应与异常处理 | 使用 `code`、`message`、`data` 返回业务结果 |
| 个人信息 | 查询、修改名称/邮箱/手机号/头像，更新前端用户状态；个人资料服务排除 `role`、`status` 更新 |
| 文件上传 | 保存文件到本地，并通过 `/uploads` 访问 |
| 修改密码 | 校验原密码、新旧密码不同，保存 bcrypt 哈希；前端成功后清除本地登录信息并跳转登录页 |
| 用户列表 | `/manager/user` 展示账号、姓名、头像、联系方式、角色与状态；支持分页、按账号或姓名搜索；查询接口要求管理员身份 |
| 用户增删改 | 管理员新增、编辑和确认删除用户；新增/编辑共用弹窗，编辑时隐藏密码；后端阻止删除当前登录账号，菜单仅管理员可见 |
| 实验室管理 | 管理员分页查询、新增、编辑、删除；支持名称查重、封面上传、容量与开放时间设置；学生不显示管理菜单 |
| 设备管理 | 管理员增删改查、名称与实验室筛选、设备图片；响应包含实验室名称，同一实验室设备名称查重 |
| 学生浏览 | 实验室卡片列表、所属设备列表、搜索分页及页面间传参 |
| 提交预约 | 实验室与设备共用预约弹窗；同日、整点/半点、至少30分钟、提前1小时至7天；检查开放时间、设备归属/状态与时间冲突，新记录待审核 |
| 我的预约、预约审核 | 下一节开发；当前创建成功不表示审核通过 |
| AI/Agent | 尚未实现 |

已有课程笔记覆盖第 6～18 节。最新的 [第18节：开发实验室预约功能](./docs/notes/18-lab-reservation.md) 按代码分段解释模型、schema、service、请求封装、组件复用、父子通信、表单校验、提交与重置，并记录数据库迁移和最终版本验证结果。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Element Plus、Axios。
- 后端：Python、FastAPI、Uvicorn、Pydantic Settings。
- 数据库：MySQL、SQLAlchemy 2、PyMySQL。
- 身份验证：PyJWT、bcrypt。

具体依赖版本见 [frontend/package.json](./frontend/package.json) 和 [backend/requirements.txt](./backend/requirements.txt)。

## 目录结构

```text
lab-system-agent/
├── README.md                 # 中文说明
├── README.en.md              # English documentation
├── .gitignore
├── docs/notes/               # 随代码提交的课程笔记
├── backend/
│   ├── .env.example          # 可提交的配置示例
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI 入口、中间件、路由与异常处理
│       ├── config.py         # 读取环境配置，设置上传目录
│       ├── database.py       # 数据库引擎、会话与模型基类
│       ├── api/              # 后端 HTTP 接口
│       ├── schemas/          # 请求、响应数据结构
│       ├── services/         # 业务逻辑
│       ├── models/           # 数据库表模型
│       ├── dependencies/     # 当前用户鉴权依赖
│       ├── common/           # 统一响应与异常
│       └── utils/            # 密码哈希与 JWT 工具
└── frontend/
    ├── .env.example
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    └── src/
        ├── api/              # 前端 HTTP 请求封装
        ├── components/       # 共用预约弹窗 ReserveDialog
        ├── utils/            # Axios、登录存储和用户状态
        ├── views/            # 登录、注册、个人信息、修改密码等页面
        ├── layouts/          # 公共布局和菜单入口
        └── router/           # 页面路由与登录守卫
```

`backend/uploads/` 为运行时上传目录，配置模块会自动创建。该目录与本地测试图片目录 `backend/pictures/` 不提交。

## 本地启动

以下命令从项目根目录开始。需要可用的 MySQL 服务，以及 Python 3.10+。前端 `package.json` 声明的 Node.js 要求是 `^22.18.0 || >=24.12.0`，并需要 npm。

### 1. 安装后端依赖

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

已有可用 Conda 环境时，可以激活该环境后安装依赖，省略新建虚拟环境的步骤。

### 2. 配置数据库与 JWT

在 MySQL 中创建数据库，例如：

```sql
CREATE DATABASE lab_system CHARACTER SET utf8mb4;
```

编辑 `backend/.env`，将示例数据库用户、密码和地址替换为自己的配置。数据库账号需要具备访问和创建项目表的权限，密码中的特殊字符需要 URL 编码。

生成本地 JWT 密钥后填入 `JWT_SECRET_KEY`：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

后端启动时会执行 `Base.metadata.create_all()`：它可以创建缺失的表，**不会自动迁移已有表结构，也不会创建 MySQL 数据库本身**。项目没有预设管理员账号，可以通过注册页面创建学生账号。

从旧版预约表升级时，需要把 `date/start_time/end_time` 迁移成两个非空 `DATETIME` 列 `start_at/end_at`；先备份、转换核对再移除旧列，完成后重启后端。全新数据库会直接按新模型创建表。详细步骤见 [第18节的迁移说明](./docs/notes/18-lab-reservation.md#第十四章-数据库迁移与运行版本)。数据库及本地备份不会随 Git 推送。

### 3. 启动后端

在 `backend` 目录、已激活的 Python 环境中执行：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- 根接口：<http://localhost:8000/>
- 接口文档：<http://localhost:8000/docs>
- 接口清单：<http://localhost:8000/openapi.json>

如果环境的文件监听配额不足，可去掉 `--reload`，修改后手动重启服务。

### 4. 启动前端

另开一个终端，从项目根目录执行：

```bash
cd frontend
npm ci
cp .env.example .env.development
npm run dev -- --host 127.0.0.1 --port 5173
```

访问 <http://localhost:5173>。`cp` 命令用于首次配置；已有 `.env` 或 `.env.development` 时保留自己的配置，不要直接覆盖。

开发环境将 `/api` 和 `/uploads` 代理到 `http://127.0.0.1:8000`。空的 `VITE_API_BASE_URL` 会使用该代理。当前布局中头像地址还使用了 `http://localhost:8000`，因此本说明按浏览器能同时访问本机 5173 和 8000 端口的方式运行。

如果在远程节点开发，需要将前后端两个端口都转发到浏览器所在电脑；不同节点的 `localhost` 指向不同机器。这里的 Vite 代理仅用于开发，生产部署需要另行配置 API 与静态文件访问地址。

### 5. 构建前端

```bash
cd frontend
npm run build
```

构建产物位于 `frontend/dist/`，不提交到源码仓库。构建成功不等于后端和数据库联调已通过。

## 常用后端接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/auth/register` | 注册用户 |
| POST | `/api/auth/login` | 登录，返回 token 与用户信息 |
| POST | `/api/auth/token` | Swagger 授权使用的表单登录入口 |
| GET | `/api/user/me` | 获取当前用户信息，需要 token |
| PUT | `/api/user/me` | 更新当前用户信息，需要 token |
| PUT | `/api/user/password` | 修改当前用户密码，需要 token |
| GET | `/api/user/list` | 管理员分页查询用户，参数为 `page`、`page_size`、`keywords`；关键词匹配账号或姓名 |
| POST | `/api/user` | 管理员新增用户 |
| PUT | `/api/user/{user_id}` | 管理员编辑指定用户的资料 |
| DELETE | `/api/user/{user_id}` | 管理员删除指定用户，禁止删除当前登录账号 |
| GET | `/api/lab/list` | 登录用户分页查询实验室，关键词匹配实验室名称 |
| POST | `/api/lab` | 管理员新增实验室，检查名称重复 |
| PUT | `/api/lab/{lab_id}` | 管理员编辑实验室，名称查重排除当前记录 |
| DELETE | `/api/lab/{lab_id}` | 管理员删除实验室 |
| GET | `/api/equipment/list` | 登录用户查询设备，支持名称关键词与 `lab_id` 筛选 |
| POST | `/api/equipment` | 管理员新增设备 |
| PUT | `/api/equipment/{equipment_id}` | 管理员编辑设备 |
| DELETE | `/api/equipment/{equipment_id}` | 管理员删除设备 |
| POST | `/api/reservation` | 登录用户创建待审核预约，提交 `lab_id`、可选 `equipment_id`、`start_at`、`end_at` 和可选备注 |
| POST | `/api/files/upload` | 上传文件，当前实现未要求鉴权 |

普通业务接口返回示例：

```json
{"code":200,"message":"请求成功","data":null}
```

业务异常可能使用 HTTP 200 返回非 200 的业务 `code`；HTTP 状态码与业务码需要分别查看。Swagger 表单登录接口和根接口采用各自的返回格式。

## 学习笔记与后续提交

课程笔记已复制到 [docs/notes](./docs/notes/)，与代码一起提交。原学习目录 `agent-lab/docs/lab-system-agent-notes/` 保留；后续在原目录写完笔记后，需要同步对应文件到 `docs/notes/` 再提交。第 6～11 节保留了当时的接口与文件名称，当前实现请以源码和本 README 为准。

后续每节课完成后，检查功能、同步笔记并更新课程进度，再按课提交。下一课是第19节“开发我的预约和预约审核”。GitHub 仓库：<https://github.com/youbih/lab-system-agent>。

```bash
git status --short
git add .
git diff --cached --stat
git commit -m "第19节：完成对应课程功能"
git push origin main
```

提交前检查暂存内容，确认没有新增真实凭据或个人文件。

## 提交前检查与当前边界

- `.env`、本地凭据、依赖目录、缓存、上传文件、测试图片、日志和数据库导出已配置忽略；`.env.example` 与 `package-lock.json` 保留提交。
- 示例配置只有占位内容。真实数据库连接、JWT 密钥、账号密码和 token 不应复制到 README、笔记、截图或提交信息。
- `VITE_*` 是可被浏览器读取的公开配置，不用于保存密钥。
- 当前是课程开发版本；清除浏览器 token 不会自动撤销其他地方持有的旧 JWT。
- 用户管理已实现本节范围内的增删改查，角色和状态可在编辑弹窗中调整；路由守卫只检查 token 是否存在，管理员权限由对应后端接口验证。整体系统仍未完成。
- 预约表使用完整日期时间并约定保存北京时间；最终创建规则限制同日、半小时刻度。开放时间辅助函数保留夜间/全天解释，管理表单配置入口的一致性仍待完善。
- 实验室与其设备目前分别查重；并发预约、设备数量分配、可用时段提前禁用等仍待完善。最终源码通过临时服务的35项curl检查及2项数据核对，前端构建通过；未把浏览器端到端点击列为已完成验证。
- 课程结束后的完善清单保存在 [第14节](./docs/notes/14-user-crud.md#附录课程结束后统一完善)、[第15节](./docs/notes/15-lab-management.md#附录课程结束后统一完善)和[第18节](./docs/notes/18-lab-reservation.md#附录课程结束后统一完善)笔记末尾，现阶段保留当前课堂实现；个人资料字段排除已在此前实施。
- 修改密码接口曾通过 curl 返回成功；旧密码失败、新密码成功等完整验证需要以实际操作结果为准。
- 上传前检查说明见 [docs/PRE_UPLOAD_REVIEW.md](./docs/PRE_UPLOAD_REVIEW.md)。
