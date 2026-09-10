from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from routes import api

app = FastAPI(title="HADIL \u2014 AI-Safe Database Query Execution Layer")

def get_allowed_origins():
    # Base default origins for local development and production single-origin HADIL.exe
    default_origins = [
        "http://localhost:5173", "http://localhost:3000",
        "http://127.0.0.1:5173", "http://127.0.0.1:3000",
        "http://localhost:8000", "http://127.0.0.1:8000"
    ]
    
    # Merge custom origins from HADIL_ALLOWED_ORIGINS or ALLOWED_ORIGINS
    env_origins_str = os.getenv("HADIL_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS", "")
    origins = list(default_origins)
    
    if env_origins_str:
        for o in env_origins_str.split(","):
            cleaned = o.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
                
    return origins

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
    return {"status": "ok", "service": "HADIL"}

app.include_router(api.router, prefix="/api")

# Serve bundled React frontend static build
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from utils.path_resolver import resolve_bundled_resource

static_dist_path = resolve_bundled_resource("frontend/dist")
if os.path.exists(static_dist_path):
    print(f"[HADIL RUNTIME] Mounting static frontend assets from: {static_dist_path}")
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dist_path, "assets")), name="static_assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        # Allow /api routes to be handled by APIRouter
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API route not found")
        
        # Check if requested static file exists in static_dist
        target_file = os.path.join(static_dist_path, full_path)
        if full_path and os.path.exists(target_file) and os.path.isfile(target_file):
            return FileResponse(target_file)
        
        # Otherwise fallback to index.html for SPA client-side routing
        return FileResponse(os.path.join(static_dist_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

