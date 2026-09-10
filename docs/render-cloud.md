# HADIL Render / cloud deployment

This branch keeps the Windows V1 desktop application intact. Cloud mode is selected with `HADIL_DEPLOYMENT_MODE=cloud` (Render also implies cloud when that variable is unset).

## Start command

From the repository root, with `PYTHONPATH=backend`:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Do not start `HADIL.exe`, `hadil_runtime.py` desktop mode, tkinter splash, or the Windows tray on Render.

## Required environment variables

- `HADIL_DEPLOYMENT_MODE=cloud`
- `HADIL_JWT_SECRET` — required, must not be the desktop development default
- `HADIL_METADATA_DATABASE_URL` — HADIL metadata PostgreSQL (Supabase). Not a customer database.
- `HADIL_ALLOWED_ORIGINS` — comma-separated browser origins if the UI is not same-origin. Do not use `*`.
- `HADIL_DATA_DIR` — writable directory for policy files, FAISS index, and embedding cache

Optional:

- `HADIL_METADATA_POOL_MODE=null` — recommended for Supabase transaction pooler (port 6543)
- `HADIL_EMBEDDING_MODEL_PATH` — pre-downloaded MiniLM directory
- `HADIL_EMBEDDING_CACHE_DIR` — Hugging Face / sentence-transformers cache
- `RENDER_EXTERNAL_URL` — added to CORS automatically when Render provides it

## Metadata vs customer databases

| Store | Purpose | Engine |
| --- | --- | --- |
| HADIL metadata | Users, RBAC, LLM config, registered DB records | Supabase PostgreSQL |
| Customer databases | Query/execution targets | Remote PostgreSQL or MySQL |

Local SQLite file registration, upload, and directory scan remain in the shared codebase but are disabled in cloud mode.

## MiniLM / RAG strategy

Model weights in `models/all-MiniLM-L6-v2/` are intentionally not in Git.

1. If `HADIL_EMBEDDING_MODEL_PATH` points at a local directory, use it.
2. Else if the Windows bundled `models/all-MiniLM-L6-v2` directory exists, use it (desktop).
3. Else if `HADIL_DATA_DIR/models/all-MiniLM-L6-v2` exists, use it.
4. Else download `all-MiniLM-L6-v2` from Hugging Face into the writable cache on first RAG use.

RAG is not disabled when the bundled folder is absent. Startup continues; the first policy index/query loads the model. If download or load fails, RAG raises instead of silently skipping.

## First administrator

Use the existing first-run setup screen (`/api/setup/status`). There is no backdoor cloud admin.

## Manual steps (not performed in this branch)

1. Create a Render web service from `cloud-render`.
2. Create a Supabase PostgreSQL database and set `HADIL_METADATA_DATABASE_URL`.
3. Set `HADIL_JWT_SECRET` and CORS origins in the Render dashboard.
4. Confirm Node.js is available in the Render build image so `npm --prefix frontend` can produce `frontend/dist`.
5. Open the Render URL and complete first-run MASTER_ADMIN setup.
6. Register customer PostgreSQL/MySQL databases from the UI.
