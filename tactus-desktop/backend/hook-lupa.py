# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller hook for lupa to ensure binary modules are correctly packaged.
"""

import glob
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import lupa

# Collect all Python files
datas = collect_data_files("lupa", include_py_files=True)

# Manually collect all .so files from lupa
lupa_dir = os.path.dirname(lupa.__file__)
binaries = [(so_file, "lupa") for so_file in glob.glob(os.path.join(lupa_dir, "*.so"))]

# Collect all submodules to ensure everything is included
hiddenimports = collect_submodules("lupa")

# Add the dynamic attributes that lupa exposes
hiddenimports.extend(
    [
        "lupa.LuaRuntime",
        "lupa.LuaError",
        "lupa.lua_type",
    ]
)
