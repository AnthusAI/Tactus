# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import glob
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs, copy_metadata

block_cipher = None

# Get the project root (parent of tactus-desktop)
project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

# Collect all tactus modules
tactus_modules = collect_submodules('tactus')
flask_modules = collect_submodules('flask')
antlr_modules = collect_submodules('antlr4')

# Collect data files
tactus_datas = collect_data_files('tactus', include_py_files=True)
antlr_datas = collect_data_files('antlr4')
lupa_datas = collect_data_files('lupa', include_py_files=True)

# Manually collect lupa native libraries
# collect_dynamic_libs doesn't find them, so we do it explicitly
import lupa
lupa_dir = os.path.dirname(lupa.__file__)
lupa_binaries = [(so_file, 'lupa') for so_file in glob.glob(os.path.join(lupa_dir, '*.so'))]

a = Analysis(
    [os.path.join(project_root, 'tactus', 'cli', 'app.py')],
    pathex=[project_root],
    binaries=lupa_binaries,
    datas=[
        *tactus_datas,
        *antlr_datas,
        *lupa_datas,
        *copy_metadata('genai_prices'),
        *copy_metadata('pydantic_ai_slim'),
        *copy_metadata('pydantic_ai'),
        *copy_metadata('pydantic'),
        *copy_metadata('openai'),
        *copy_metadata('anthropic'),
        (os.path.join(project_root, 'tactus', 'validation', 'grammar', '*.g4'), 'tactus/validation/grammar'),
        (os.path.join(project_root, 'tactus-ide', 'frontend', 'dist'), 'tactus-ide/frontend/dist'),
    ],
    hiddenimports=[
        *tactus_modules,
        *flask_modules,
        *antlr_modules,
        'lupa',
        'flask_cors',
        'pydantic',
        'pydantic_ai',
        'boto3',
        'botocore',
        'openai',
        'typer',
        'rich',
        'dotyaml',
        'genai_prices',
    ],
    hookspath=[os.path.join(SPECPATH)],  # Use custom hooks from this directory
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='tactus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='tactus',
)
