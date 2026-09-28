# HADIL Cloud (Render)

This is the **cloud-render** branch: HADIL as a hosted web service. It is not the Windows desktop EXE.

HADIL is an AI-safe database query layer. Users ask questions in natural language; the service generates SQL, verifies intent, and blocks unsafe execution before anything hits a customer database.

```text
Browser → FastAPI (backend/) → AI providers → customer PostgreSQL/MySQL
```

## Repository layout

| Folder | Contents |
| --- | --- |
| `backend/` | FastAPI app, auth, RBAC, query pipeline, tests |
| `frontend/` | React + Vite UI |
| `deploy/` | Render Blueprint (`render.yaml`) and `deploy/.env.example` |

Do not run `HADIL.exe`, PyInstaller, the tray app, or desktop splash on this branch.

## Local development

Prerequisites: Python 3.12, Node.js 20, Git.

```powershell
git clone -b cloud-render https://github.com/SarJata/HADIL.git
cd HADIL
```

**Backend** (from the repo root)

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\activate
pip install -r backend\requirements.txt
copy deploy\.env.example backend\.env
```

Edit `backend/.env` (never commit it). For a local cloud-shaped run:

```env
HADIL_DEPLOYMENT_MODE=cloud
HADIL_JWT_SECRET=replace-with-a-long-random-secret
HADIL_METADATA_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/postgres
HADIL_ALLOWED_ORIGINS=http://localhost:5173
```

```powershell
uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

API docs: `http://localhost:8000/docs`.

**Frontend**

```powershell
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:8000
```

```powershell
npm run dev
```

UI: `http://localhost:5173`.

## Render

Create a **Python** web service from this branch. Render’s Blueprint file lives at `deploy/render.yaml` (not the repo root). If Blueprint auto-detect does not pick it up, paste these commands in the dashboard:

**Build**

```text
pip install -r backend/requirements.txt && npm --prefix frontend ci && npm --prefix frontend run build && mkdir -p backend/static_frontend && cp -a frontend/dist/. backend/static_frontend/
```

**Start**

```text
uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT
```

Do not use `uvicorn backend.main:app`.

### Required environment variables

Set these in the Render dashboard. Never commit real values.

| Variable | Purpose |
| --- | --- |
| `HADIL_DEPLOYMENT_MODE` | `cloud` (set in `deploy/render.yaml`) |
| `HADIL_JWT_SECRET` | Signing secret; must not be the desktop default |
| `HADIL_METADATA_DATABASE_URL` | HADIL metadata PostgreSQL (for example Supabase). Not a customer database. |
| `HADIL_ALLOWED_ORIGINS` | Comma-separated browser origins if the UI is not same-origin. Do not use `*`. |
| `HADIL_DATA_DIR` | Writable dir for policy files, FAISS, embedding cache |

HADIL-owned provider keys (enable only the providers you offer):

- `HADIL_GEMINI_API_KEY`
- `HADIL_OPENAI_API_KEY`
- `HADIL_ANTHROPIC_API_KEY`
- `HADIL_SARVAM_API_KEY`

Optional: `HADIL_METADATA_POOL_MODE=null` for the Supabase transaction pooler (port 6543); `HADIL_EMBEDDING_MODEL_PATH` / `HADIL_EMBEDDING_CACHE_DIR` for MiniLM; `RENDER_EXTERNAL_URL` is added to CORS when Render provides it.

### Metadata vs customer databases

| Store | Purpose |
| --- | --- |
| HADIL metadata | Users, RBAC, platform AI policy, org provider selection |
| Customer databases | Query targets (remote PostgreSQL or MySQL only in cloud) |

Local SQLite upload/scan exists in the shared codebase but is disabled in cloud mode.

### First administrator

Open the Render URL and complete first-run setup (`/api/setup/status`). There is no backdoor admin.

Then: register customer databases in the UI, add provider keys on Render, enable providers for organizations in the platform UI.

## Desktop Windows build

Use the **windows-build** branch, not this one.
