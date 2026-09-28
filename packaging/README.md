# Packaging

Windows EXE pipeline. Run from the repository root:

```powershell
py packaging\build.py
```

`HADIL.spec` treats this folder as `SPECPATH` and the parent directory as the project root (`backend/`, `frontend/`, `models/`).
