# 智能实验室预约系统 · 全栈学习项目

[中文](./README.md) | [English](./README.en.md)

跟随课程逐步开发的前后端分离项目，目标是构建实验室预约系统。目前完成到**第 12 节：开发用户修改密码功能**，已实现用户账户与个人中心相关功能。

这是课程学习中的阶段版本，实验室、设备、用户管理和预约业务尚未完成；项目目前也没有接入 AI/Agent 功能。

## 已有功能与课程进度

| 功能 | 当前状态 |
|---|---|
| 用户注册、登录 | 已有实现；注册用户默认为学生 |
| JWT 身份验证 | 后端检查 token 和用户状态，前端保存 token 并随请求携带 |
| 统一响应与异常处理 | 使用 `code`、`message`、`data` 返回业务结果 |
| 个人信息 | 查询、修改名称/邮箱/手机号/头像，更新前端用户状态 |
| 文件上传 | 保存文件到本地，并通过 `/uploads` 访问 |
| 修改密码 | 校验原密码、新旧密码不同，保存 bcrypt 哈希；前端成功后清除本地登录信息并跳转登录页 |
| 实验室、设备、用户管理 | 占位页面，功能待开发；设备和用户管理入口尚无对应路由 |
| 预约、AI/Agent | 尚未实现 |

已有课程笔记覆盖第 6～12 节：JWT、统一响应与异常、Axios 对接、注册与 Service 分层、文件上传、个人信息修改、密码修改。

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
| POST | `/api/files/upload` | 上传文件，当前实现未要求鉴权 |

普通业务接口返回示例：

```json
{"code":200,"message":"请求成功","data":null}
```

业务异常可能使用 HTTP 200 返回非 200 的业务 `code`；HTTP 状态码与业务码需要分别查看。Swagger 表单登录接口和根接口采用各自的返回格式。

## 学习笔记与后续提交

课程笔记已复制到 [docs/notes](./docs/notes/)，与代码一起提交。原学习目录 `agent-lab/docs/lab-system-agent-notes/` 保留；后续在原目录写完笔记后，需要同步对应文件到 `docs/notes/` 再提交。第 6～11 节保留了当时的接口与文件名称，当前实现请以源码和本 README 为准。

后续每节课完成后，检查功能、同步笔记并更新课程进度，再按课提交，例如 `第13节：完成对应课程功能`。GitHub 仓库：<https://github.com/youbih/lab-system-agent>。

```bash
git status --short
git add .
git diff --cached --stat
git commit -m "第13节：完成对应课程功能"
git push origin main
```

提交前检查暂存内容，确认没有新增真实凭据或个人文件。

## 提交前检查与当前边界

- `.env`、本地凭据、依赖目录、缓存、上传文件、测试图片、日志和数据库导出已配置忽略；`.env.example` 与 `package-lock.json` 保留提交。
- 示例配置只有占位内容。真实数据库连接、JWT 密钥、账号密码和 token 不应复制到 README、笔记、截图或提交信息。
- `VITE_*` 是可被浏览器读取的公开配置，不用于保存密钥。
- 当前是课程开发版本；清除浏览器 token 不会自动撤销其他地方持有的旧 JWT。
- 修改密码接口曾通过 curl 返回成功；旧密码失败、新密码成功等完整验证需要以实际操作结果为准。
- 上传前检查说明见 [docs/PRE_UPLOAD_REVIEW.md](./docs/PRE_UPLOAD_REVIEW.md)。
