# Smart Laboratory Reservation System · Full-Stack Learning Project

[中文](./README.md) | [English](./README.en.md)

A course-driven project with a Vue frontend and a FastAPI backend. Development has reached **Lesson 13: User List Display**. The current implementation covers accounts, profiles, and administrator user-list queries.

Laboratory management, equipment management, reservations, and other user administration operations remain unfinished. AI/Agent functionality has not been integrated.

## Features and course progress

| Feature | Current status |
|---|---|
| Registration and login | Implemented; registered users receive the student role |
| JWT authentication | Backend validates tokens and user status; frontend stores and attaches tokens |
| Shared responses and exception handling | Business responses use `code`, `message`, and `data` |
| User profile | Read and update name, email, phone, and avatar; synchronize frontend user state |
| File uploads | Local file storage with access through `/uploads` |
| Password updates | Verify the current password, reject an identical new password, store a bcrypt hash; frontend clears local credentials and redirects to login on success |
| User list | `/manager/user` displays accounts, names, avatars, contact details, roles, and status; supports pagination and account/name keyword searches; backend queries require an administrator |
| Laboratories and equipment | Placeholder pages; the equipment management menu entry has no matching route yet |
| Reservations and AI/Agent | Not implemented |

Existing notes cover Lessons 6–13: JWT, responses and exceptions, Axios integration, registration and service layers, uploads, profiles, password updates, and user lists. Lessons 6–12 now include detailed explanations following code execution order.

## Technology

- Frontend: Vue 3, Vite, Vue Router, Element Plus, Axios.
- Backend: Python, FastAPI, Uvicorn, Pydantic Settings.
- Database: MySQL, SQLAlchemy 2, PyMySQL.
- Authentication: PyJWT and bcrypt.

See [frontend/package.json](./frontend/package.json) and [backend/requirements.txt](./backend/requirements.txt) for dependencies.

## Layout

```text
lab-system-agent/
├── README.md                 # Chinese documentation
├── README.en.md              # English documentation
├── .gitignore
├── docs/notes/               # Course notes committed with the code
├── backend/
│   ├── .env.example          # Configuration placeholders
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI entry point and application setup
│       ├── config.py         # Environment settings and upload configuration
│       ├── database.py       # Engine, sessions, and base model
│       ├── api/              # HTTP endpoints
│       ├── schemas/          # Request and response schemas
│       ├── services/         # Business logic
│       ├── models/           # Database models
│       ├── dependencies/     # Authentication dependencies
│       ├── common/           # Responses and exceptions
│       └── utils/            # Password and JWT helpers
└── frontend/
    ├── .env.example
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    └── src/
        ├── api/              # HTTP request wrappers
        ├── utils/            # Axios, local credentials, and user state
        ├── views/            # Login, registration, profile, password, etc.
        ├── layouts/          # Shared layout and navigation
        └── router/           # Routes and authentication guard
```

Configuration creates `backend/uploads/` automatically. Uploads and the local test pictures in `backend/pictures/` are excluded from version control.

## Run locally

Start from the project root. You need MySQL, Python 3.10+, npm, and a Node.js version matching the frontend's declared range: `^22.18.0 || >=24.12.0`.

### 1. Install backend dependencies

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

You can use an existing Conda environment instead of creating a virtual environment.

### 2. Configure MySQL and JWT

Create the database in MySQL:

```sql
CREATE DATABASE lab_system CHARACTER SET utf8mb4;
```

Edit `backend/.env` with your database credentials and address. The database user needs access to the database and permission to create project tables. URL-encode special characters in connection-string credentials.

Generate a local signing secret and put it in `JWT_SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

On startup, `Base.metadata.create_all()` creates missing tables. It does not migrate existing tables or create the MySQL database itself. There is no seeded administrator account; registration creates a student account.

### 3. Start the backend

From `backend`, with your Python environment active:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Root endpoint: <http://localhost:8000/>
- API documentation: <http://localhost:8000/docs>
- OpenAPI schema: <http://localhost:8000/openapi.json>

If file-watcher limits prevent reloading, omit `--reload` and restart manually after changes.

### 4. Start the frontend

Open another terminal and start from the project root:

```bash
cd frontend
npm ci
cp .env.example .env.development
npm run dev -- --host 127.0.0.1 --port 5173
```

Visit <http://localhost:5173>. Copy environment examples only during initial setup; preserve existing `.env` and `.env.development` files rather than overwriting local settings.

Vite proxies `/api` and `/uploads` to `http://127.0.0.1:8000`. An empty `VITE_API_BASE_URL` uses this proxy. The current layout also prefixes avatar URLs with `http://localhost:8000`, so the browser must be able to reach both local ports.

For remote development, forward both frontend and backend ports to your browser's machine. `localhost` refers to a different machine on each node. The Vite proxy is for development; production API and file routing require separate configuration.

### 5. Build the frontend

```bash
cd frontend
npm run build
```

Output is written to `frontend/dist/` and excluded from source control. A successful frontend build does not verify backend or database integration.

## Backend endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register a user |
| POST | `/api/auth/login` | Return a token and user information |
| POST | `/api/auth/token` | Form login for Swagger authorization |
| GET | `/api/user/me` | Read the authenticated user's profile |
| PUT | `/api/user/me` | Update the authenticated user's profile |
| PUT | `/api/user/password` | Update the authenticated user's password |
| GET | `/api/user/list` | Administrator user queries with `page`, `page_size`, and `keywords`; keywords match account or name |
| POST | `/api/files/upload` | Upload a file; currently does not require authentication |

Typical business response:

```json
{"code":200,"message":"请求成功","data":null}
```

Business exceptions can return HTTP 200 with a non-200 business `code`. Inspect both the HTTP status and response body. The Swagger token endpoint and root endpoint use their own response formats.

## Notes and lesson commits

Course notes have been copied into [docs/notes](./docs/notes/) to be committed with the code. The original learning directory at `agent-lab/docs/lab-system-agent-notes/` is preserved. After editing notes there, synchronize the relevant files into `docs/notes/` before committing. Lessons 6–11 retain historical endpoint and file names; use the current source and this README for the latest implementation.

After each lesson, verify the feature, synchronize notes, update course progress, and commit the changes. GitHub repository: <https://github.com/youbih/lab-system-agent>.

```bash
git status --short
git add .
git diff --cached --stat
git commit -m "Lesson 14: complete the lesson feature"
git push origin main
```

Review staged changes for credentials or personal files before committing.

## Before publishing and current limitations

- Ignore rules exclude real environment files, local credentials, dependencies, caches, uploads, test pictures, logs, and database exports. Configuration examples and `package-lock.json` remain eligible for commits.
- Examples contain placeholders. Keep actual credentials, signing secrets, passwords, and tokens out of documentation, screenshots, and commit messages.
- `VITE_*` variables are public browser configuration, not secret storage.
- This is a course development snapshot. Clearing local credentials does not revoke JWTs held elsewhere.
- User administration currently provides listing and searching, without create/edit/delete/status controls. The frontend route guard checks token presence; the backend query endpoint enforces the administrator role.
- The password endpoint returned success in a user-run curl check. The full old-password/new-password login verification still requires actual confirmation.
- See [docs/PRE_UPLOAD_REVIEW.md](./docs/PRE_UPLOAD_REVIEW.md) for the preparation record in Chinese.
