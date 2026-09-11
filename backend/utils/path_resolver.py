import os
import sys

def is_frozen() -> bool:
    """Check if the application is running inside a PyInstaller binary bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def get_bundle_dir() -> str:
    """
    Returns the root directory for read-only bundled application resources.
    - In PyInstaller executable: returns sys._MEIPASS
    - In development: returns HADIL repository root directory
    """
    if is_frozen():
        return getattr(sys, '_MEIPASS')
    # Default development root (parent of backend directory)
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_file_dir, "..", ".."))

def get_user_data_dir() -> str:
    """
    Returns the root directory for writable user runtime data.
    Order of precedence:
    1. HADIL_DATA_DIR environment variable
    2. %APPDATA%/HADIL (Windows) or ~/.hadil (macOS/Linux)
    3. Fallback to repository root in development if explicitly desired
    """
    env_dir = os.getenv("HADIL_DATA_DIR")
    if env_dir:
        target = os.path.abspath(env_dir)
    else:
        if sys.platform == "win32":
            appdata = os.getenv("APPDATA", os.path.expanduser("~"))
            target = os.path.join(appdata, "HADIL")
        else:
            target = os.path.join(os.path.expanduser("~"), ".hadil")
    
    os.makedirs(target, exist_ok=True)
    return target

def resolve_bundled_resource(relative_path: str) -> str:
    """Resolves path for read-only bundled resources (e.g. frontend static dist, bundled ML model)."""
    clean_path = relative_path.lstrip("/\\")
    return os.path.join(get_bundle_dir(), clean_path)


def _is_frontend_dist(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "index.html"))


def resolve_frontend_dist() -> str:
    """
    Locate the Vite production build (frontend/dist) for same-origin SPA serving.

    Frozen Windows builds keep the PyInstaller _MEIPASS layout.
    Cloud/source runs also search cwd and ancestors so Render's repo-root
    working directory is found even if __file__ is not two levels below root.
    """
    relative = os.path.join("frontend", "dist")
    if is_frozen():
        return os.path.join(get_bundle_dir(), relative)

    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(here, ".."))
    repo_from_file = os.path.abspath(os.path.join(here, "..", ".."))
    candidates = [
        os.path.join(repo_from_file, relative),
        os.path.join(os.path.abspath(os.getcwd()), relative),
        # Render copies Vite output here so gitignored frontend/dist still serves.
        os.path.join(backend_dir, "static_frontend"),
    ]
    for start in (here, os.getcwd()):
        cur = os.path.abspath(start)
        for _ in range(8):
            candidates.append(os.path.join(cur, relative))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

    seen = set()
    for path in candidates:
        normalized = os.path.abspath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if _is_frontend_dist(normalized):
            return normalized
    return os.path.join(repo_from_file, relative)

def resolve_user_data_resource(relative_path: str) -> str:
    """Resolves path for writable persistent user resources (e.g. metadata db, policy docs, faiss index)."""
    clean_path = relative_path.lstrip("/\\")
    target_path = os.path.join(get_user_data_dir(), clean_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    return target_path

def get_default_database_folder() -> str:
    """
    Returns the authoritative default folder for SQLite databases.
    Order of precedence:
    1. DATABASE_FOLDER environment variable if explicitly set
    2. %APPDATA%/HADIL/databases in production/packaged mode (or when frozen)
    3. Fallback to ./databases in development mode if present
    """
    env_folder = os.getenv("DATABASE_FOLDER")
    if env_folder:
        return os.path.abspath(env_folder)
    if is_frozen():
        target = os.path.join(get_user_data_dir(), "databases")
        os.makedirs(target, exist_ok=True)
        return target
    # In source development mode, prefer local ./databases if directory exists or default to runtime data dir
    dev_databases = os.path.abspath("./databases")
    if os.path.exists(dev_databases):
        return dev_databases
    target = os.path.join(get_user_data_dir(), "databases")
    os.makedirs(target, exist_ok=True)
    return target

