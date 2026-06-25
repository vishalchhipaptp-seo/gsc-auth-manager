@echo off
title GSC Auth Manager
echo.
echo  GSC Auth Manager - Starting...
echo  ==============================
echo.

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel%==0 (
    echo  [OK] Python found
    goto :install_deps
)

py --version >nul 2>&1
if %errorlevel%==0 (
    echo  [OK] Python found (py launcher)
    set "PYTHON_CMD=py"
    goto :install_deps_py
)

:: Python not found — auto install
echo  [!] Python not found. Installing automatically...
echo.

:: Download Python installer
set "PY_VERSION=3.12.7"
set "PY_INSTALLER=python-%PY_VERSION%-amd64.exe"
set "PY_URL=https://www.python.org/ftp/python/%PY_VERSION%/%PY_INSTALLER%"

echo  Downloading Python %PY_VERSION%...
powershell -Command "& { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%~dp0%PY_INSTALLER%' }" 2>nul

if not exist "%~dp0%PY_INSTALLER%" (
    echo.
    echo  [ERROR] Could not download Python installer.
    echo  Please install Python manually from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo  Installing Python (this may take a minute)...
"%~dp0%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0

:: Wait for install to finish
timeout /t 3 /nobreak >nul

:: Clean up installer
del "%~dp0%PY_INSTALLER%" >nul 2>&1

:: Refresh PATH so we can find python
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python installed but not found in PATH.
    echo  Please close this window, open a NEW command prompt, and run run.bat again.
    pause
    exit /b 1
)

echo  [OK] Python installed successfully
echo.

:install_deps
set "PYTHON_CMD=python"
goto :do_install

:install_deps_py
set "PYTHON_CMD=py"
goto :do_install

:do_install
echo  Installing dependencies...
%PYTHON_CMD% -m pip install --upgrade pip >nul 2>&1
%PYTHON_CMD% -m pip install flask patchright pywebview requests >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Retrying dependency install...
    %PYTHON_CMD% -m pip install flask patchright pywebview requests
)

echo.
echo  [OK] All ready - launching app...
echo.
%PYTHON_CMD% app.py
