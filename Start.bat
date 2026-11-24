@echo off
title Joint Title Bar Maker
cd /d "%~dp0"
set PY=
set PYW=
where py >nul 2>nul && set PY=py&& set PYW=pyw
if not defined PY where python >nul 2>nul && set PY=python&& set PYW=pythonw
if not defined PY (
  echo Python is not installed.
  echo Get it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH" when installing^)
  pause
  exit /b 1
)
%PY% -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo First run: installing Pillow ^(the image library this tool needs^)...
  %PY% -m pip install --user pillow
  if errorlevel 1 (
    echo Could not install Pillow. Run this yourself:  %PY% -m pip install pillow
    pause
    exit /b 1
  )
)
start "" %PYW% titlebar_maker.pyw
