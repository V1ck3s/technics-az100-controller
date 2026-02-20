# /// script
# requires-python = ">=3.11"
# dependencies = ["pyinstaller>=6.0", "customtkinter>=5.2"]
# ///
"""
Build technics_gui.py en executable Windows (.exe).

Usage : uv run build_gui.py
Produit : dist/technics_gui.exe
"""

import os
import subprocess
import sys
from pathlib import Path

import customtkinter


def main():
    root = Path(__file__).parent
    script = root / "technics_gui.py"
    ctk_path = Path(customtkinter.__file__).parent

    if not script.exists():
        print(f"Erreur: {script} introuvable", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "technics_gui",
        "--add-data", f"{ctk_path}{os.pathsep}customtkinter/",
        "--hidden-import", "customtkinter",
        str(script),
    ]

    print(f"Build: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(root))
    if result.returncode == 0:
        exe = root / "dist" / "technics_gui.exe"
        print(f"\nBuild OK: {exe}")
    else:
        print("\nBuild echoue", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
