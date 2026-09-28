# HADIL Windows desktop

This is the **windows-build** branch: HADIL as a local Windows application (and a PyInstaller `HADIL.exe`). It is not the Render cloud service.

HADIL is an AI-safe database query layer. Users ask questions in natural language; the app generates SQL, verifies intent, and blocks unsafe execution before anything hits a database.

```text
React UI → FastAPI (bundled or local) → AI modules → SQLite / PostgreSQL / MySQL
```

## Repository layout

| Folder | Contents |
| --- | --- |
| `backend/` | FastAPI app, desktop runtime, tests |
| `frontend/` | React + Vite UI |
| `packaging/` | `build.py`, `HADIL.spec`, `hadil.ico` |
| `models/` | Place MiniLM weights here before building the EXE (weights are not in Git) |

## Local development

Prerequisites: Python 3.12, Node.js 20, Git. On Windows, `py` launcher is used by the packaging script.

```powershell
git clone -b windows-build https://github.com/SarJata/HADIL.git
cd HADIL
```

**Backend**

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\activate
pip install -r backend\requirements.txt
```

Create `backend/.env` (never commit it):

```env
HADIL_DEPLOYMENT_MODE=desktop
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_FOLDER=./databases
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

From the repo root:

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

## Build HADIL.exe

1. Install Windows packaging extras if your `backend/requirements.txt` does not already include PyInstaller, pystray, and related desktop packages.
2. Download `all-MiniLM-L6-v2` into `models/all-MiniLM-L6-v2/` so `model.safetensors` exists. This folder is gitignored (~87MB).
3. From the repo root:

```powershell
py packaging\build.py
```

The pipeline builds `frontend/dist`, runs PyInstaller with `packaging/HADIL.spec`, and writes `dist/HADIL.exe`. `build/` and `dist/` are gitignored.

Do not commit `.env` files, API keys, or `.exe` artifacts.

## Cloud / Render

Use the **cloud-render** branch, not this one.
