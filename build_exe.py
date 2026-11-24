"""Build "Joint Title Bar Maker.exe" (one file, no Python needed) with PyInstaller.

    py -3.13 build_exe.py

Makes its own venv in build/ with PyInstaller and Pillow, so your Python stays untouched.
On Python 3.13 a venv can't find Tcl/Tk by itself, so TCL_LIBRARY and TK_LIBRARY are pointed at the base install;
without that the .exe would start without tkinter.
"""
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "build"
NAME = "Joint Title Bar Maker"


def main():
    base = Path(sys.base_prefix)
    env = dict(os.environ, TCL_LIBRARY=str(base / "tcl/tcl8.6"), TK_LIBRARY=str(base / "tcl/tk8.6"))
    py = WORK / "venv/Scripts/python.exe"
    if not py.exists():
        subprocess.run([sys.executable, "-m", "venv", str(WORK / "venv")], check=True)
        subprocess.run([str(py), "-m", "pip", "install", "--quiet", "pyinstaller", "pillow"], check=True)
    subprocess.run([str(py), "-c", "import tkinter; tkinter.Tcl()"], check=True, env=env)
    subprocess.run([str(py), "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", NAME,
                    "--icon", str(ROOT / "app.ico"), "--add-data", "%s;." % (ROOT / "app.ico"), "--paths", str(ROOT),
                    "--distpath", str(ROOT / "dist"), "--workpath", str(WORK / "pyinstaller"), "--specpath", str(WORK),
                    str(ROOT / "titlebar_maker.pyw")], check=True, env=env)
    exe = ROOT / "dist" / (NAME + ".exe")
    with zipfile.ZipFile(ROOT / "dist/Joint-Title-Bar-Maker.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, "%s/%s.exe" % (NAME, NAME))
    print("built", exe)


if __name__ == "__main__":
    main()
