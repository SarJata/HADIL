from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

load_dotenv()

from config.deployment import get_deployment_config
from routes import api

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_deployment_config().validate_cloud_runtime()
    yield

app = FastAPI(title="HADIL \u2014 AI-Safe Database Query Execution Layer", lifespan=lifespan)

def get_allowed_origins():
    return get_deployment_config().cors_origins()

ALLOWED_ORIGINS = get_allowed_origins()

print("==================================================")
print("[HADIL CORS LOG] Configured CORS origins:")
for origin in ALLOWED_ORIGINS:
    print(f"  - {origin}")
print("==================================================")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning", "X-Requested-With"],
)

@app.get("/health")
def health_check():
    cfg = get_deployment_config()
    return {
        "status": "ok",
        "service": "HADIL",
        "deployment_mode": cfg.mode,
    }

app.include_router(api.router, prefix="/api")

# Serve bundled React frontend static build (same origin as /api and /docs).
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from utils.path_resolver import resolve_frontend_dist

static_dist_path = resolve_frontend_dist()
index_html_path = os.path.join(static_dist_path, "index.html")
if os.path.isfile(index_html_path):
    print(f"[HADIL RUNTIME] Mounting static frontend assets from: {static_dist_path}")
    assets_dir = os.path.join(static_dist_path, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static_assets")

    _SPA_RESERVED = {"docs", "redoc", "openapi.json", "health"}

    @app.get("/", include_in_schema=False)
    async def serve_spa_root():
        return FileResponse(index_html_path)

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        # Allow /api routes to be handled by APIRouter
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API route not found")
        if full_path in _SPA_RESERVED:
            raise HTTPException(status_code=404, detail="Not Found")

        # Check if requested static file exists in static_dist
        target_file = os.path.join(static_dist_path, full_path)
        if full_path and os.path.exists(target_file) and os.path.isfile(target_file):
            return FileResponse(target_file)

        # Otherwise fallback to index.html for SPA client-side routing
        return FileResponse(index_html_path)
else:
    print(
        f"[HADIL RUNTIME] Frontend dist not found at {static_dist_path!r} "
        f"(cwd={os.getcwd()!r}). GET / will not serve the React app."
    )

if __name__ == "__main__":
    import uvicorn
    cfg = get_deployment_config()
    host = cfg.bind_host if cfg.is_cloud else "0.0.0.0"
    uvicorn.run("main:app", host=host, port=cfg.bind_port, reload=cfg.is_desktop)

