@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Se placer dans le dossier du .bat
cd /d "%~dp0"

REM UTF-8 (si dispo)
chcp 65001 >nul 2>nul

echo === Rectify Perspective - Installation ===
echo Dossier: %CD%
echo.

REM --- Trouver Python ---
set "PY="
where py >nul 2>nul
if !errorlevel! == 0 (
    set "PY=py -3"
) else (
    where python >nul 2>nul
    if !errorlevel! == 0 (
        set "PY=python"
    )
)

if not defined PY (
    echo ERREUR: Python introuvable.
    echo - Installe Python 3.11+ depuis python.org
    echo - Coche "Add Python to PATH" a l'installation
    echo - Ou verifie que la commande "py" existe.
    echo.
    pause
    exit /b 1
)

REM --- Verifier version Python 3.11+ ---
set "CHECK_VER=%TEMP%\rectify_check_py_ver.py"
echo import sys > "%CHECK_VER%"
echo sys.exit(0 if sys.version_info ^>= ^(3,11^) else 1^) >> "%CHECK_VER%"
%PY% "%CHECK_VER%"
if errorlevel 1 (
    del "%CHECK_VER%" 2>nul
    echo ERREUR: Python 3.11+ requis. Version detectee:
    %PY% --version
    echo.
    pause
    exit /b 1
)
del "%CHECK_VER%" 2>nul
echo Python detecte:
%PY% --version
echo.

REM --- Creer venv si absent ---
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel (.venv)...
    %PY% -m venv ".venv"
    if errorlevel 1 (
        echo ERREUR: Impossible de creer le venv.
        pause
        exit /b 1
    )
)

REM --- Utiliser le python du venv (pas besoin d'activer pour installer) ---
set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo ERREUR: Python du venv introuvable: %VPY%
    pause
    exit /b 1
)

echo Mise a jour de pip/setuptools/wheel...
"%VPY%" -m ensurepip --upgrade >nul 2>nul
"%VPY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERREUR: echec mise a jour pip.
    pause
    exit /b 1
)

echo Installation des dependances (requirements.txt)...
"%VPY%" -m pip install -r "requirements.txt"
if errorlevel 1 (
    echo ERREUR: echec installation dependances.
    pause
    exit /b 1
)

echo.
echo Installation OK.
echo Lance l'application avec: run.bat
pause
exit /b 0
