# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import glob
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    collect_dynamic_libs,
    copy_metadata,
)

block_cipher = None

# Get the project root (parent of tactus-desktop)
project_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))

def _safe_copy_metadata(package_name: str):
    try:
        return copy_metadata(package_name)
    except Exception:
        return []


def _safe_collect_submodules(package_name: str):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def _collect_data_files(package_name: str, include_py_files: bool = False):
    try:
        return collect_data_files(package_name, include_py_files=include_py_files)
    except Exception:
        return []


# Collect modules
tactus_modules = _safe_collect_submodules("tactus")
flask_modules = _safe_collect_submodules("flask")
antlr_modules = _safe_collect_submodules("antlr4")
litellm_modules = _safe_collect_submodules("litellm")
pydantic_ai_modules = _safe_collect_submodules("pydantic_ai")

# Collect data files
tactus_data_files = _collect_data_files("tactus", include_py_files=True)
antlr_data_files = _collect_data_files("antlr4")
lupa_data_files = _collect_data_files("lupa", include_py_files=True)
behave_data_files = _collect_data_files("behave")
gherkin_data_files = _collect_data_files("gherkin")
litellm_data_files = _collect_data_files("litellm")
rfc3987_syntax_data_files = _collect_data_files("rfc3987_syntax")

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
        *tactus_data_files,
        *antlr_data_files,
        *lupa_data_files,
        *behave_data_files,
        *gherkin_data_files,
        *litellm_data_files,
        *rfc3987_syntax_data_files,
        *_safe_copy_metadata('genai_prices'),
        *_safe_copy_metadata('pydantic_ai_slim'),
        *_safe_copy_metadata('pydantic_ai'),
        *_safe_copy_metadata('pydantic'),
        *_safe_copy_metadata('openai'),
        *_safe_copy_metadata('anthropic'),
        (os.path.join(project_root, 'tactus', 'validation', 'grammar', '*.g4'), 'tactus/validation/grammar'),
        (os.path.join(project_root, 'tactus-ide', 'frontend', 'dist'), 'tactus-ide/frontend/dist'),
    ],
    hiddenimports=[
        *tactus_modules,
        *flask_modules,
        *antlr_modules,
        *litellm_modules,
        *pydantic_ai_modules,
        'litellm.litellm_core_utils.tokenizers',
        'lupa',
        'flask_cors',
        'pydantic',
        'pydantic_ai',
        'pydantic_ai.toolsets',
        'pydantic_ai.mcp',
        'boto3',
        'botocore',
        'openai',
        'typer',
        'rich',
        'dotyaml',
        'genai_prices',
        'behave',
        'gherkin',
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
