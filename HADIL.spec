# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

project_root = os.path.abspath(SPECPATH)
backend_path = os.path.join(project_root, 'backend')

# Explicit Read-Only Bundled Data Files
datas = [
    (os.path.join(project_root, 'frontend', 'dist'), os.path.join('frontend', 'dist')),
    (os.path.join(project_root, 'models', 'all-MiniLM-L6-v2'), os.path.join('models', 'all-MiniLM-L6-v2')),
]

# Targeted data collection (Avoid collect_data_files('torch') which collects tens of thousands of unused files)
datas += collect_data_files('sentence_transformers')

# Collect dynamic native libraries for PyTorch
binaries = collect_dynamic_libs('torch')

# Explicit Hidden Imports Required for HADIL Runtime
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.mysql',
    'pymysql',
    'psycopg2',
    'faiss',

    'sentence_transformers',
    'torch',
    'pypdf',
    'docx',
    'cryptography',
    'cryptography.fernet',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'tkinter',
    '_tkinter',
]

# Explicit Exclusions to guarantee clean payload (0 test DBs, 0 dev DBs, 0 test files, no huge unused ML subsystems)
excludes = [
    'pytest',
    'unittest',
    'backend.tests',
    'tests',
    'matplotlib',
    'IPython',
    'notebook',
    'tensorboard',
    'torch.utils.tensorboard',
    'torch.cuda',
    'torch.distributed',
]

a = Analysis(
    [os.path.join(backend_path, 'hadil_runtime.py')],
    pathex=[project_root, backend_path],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HADIL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'hadil.ico'),
)


