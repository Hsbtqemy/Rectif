@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Se placer dans le dossier du .bat
cd /d "%~dp0"

REM UTF-8 (si dispo)
chcp 65001 >nul 2>nul

REM Garder la fenetre ouverte en cas d'erreur (pour debug)
if "%~1"=="--debug" (
    title Rectify - Installation (mode debug)
)

echo === Rectify Perspective - Installation ===
echo Dossier: %CD%
echo.

REM --- Trouver Python (python prioritaire, py -3 en secours) ---
set "PY="
where python >nul 2>nul
if !errorlevel! == 0 (
    set "PY=python"
) else (
    where py >nul 2>nul
    if !errorlevel! == 0 (
        set "PY=py -3"
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
set "CHECK_RES=%TEMP%\rectify_check_result.txt"
echo import sys, os > "%CHECK_VER%"
echo m,n = sys.version_info[0], sys.version_info[1] >> "%CHECK_VER%"
echo ok = m ^> 3 or m == 3 and n ^>= 11 >> "%CHECK_VER%"
echo p = os.path.join^(os.environ.get^("TEMP",""^), "rectify_check_result.txt"^) >> "%CHECK_VER%"
echo open^(p, "w"^).write^("1" if ok else "0"^) >> "%CHECK_VER%"
%PY% "%CHECK_VER%"
if not exist "%CHECK_RES%" (
    del "%CHECK_VER%" 2>nul
    echo ERREUR: Python 3.11+ requis.
    pause
    exit /b 1
)
set /p VER_OK=<"%CHECK_RES%"
del "%CHECK_VER%" "%CHECK_RES%" 2>nul
if not "!VER_OK!"=="1" (
    echo ERREUR: Python 3.11+ requis.
    %PY% --version
    echo.
    pause
    exit /b 1
)
echo Python detecte:
%PY% --version
echo.

REM --- Creer venv si absent ---
if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement virtuel (.venv)...
    echo Commande: %PY% -m venv ".venv"
    %PY% -m venv ".venv"
    if errorlevel 1 (
        echo ERREUR: Impossible de creer le venv.
        echo - Verifiez les droits d'ecriture dans: %CD%
        echo - Desactivez temporairement l'antivirus si besoin
        pause
        exit /b 1
    )
    if not exist ".venv\Scripts\python.exe" (
        echo ERREUR: Le venv a ete cree mais python.exe est absent.
        echo Suppression du venv incomplet...
        rmdir /s /q ".venv" 2>nul
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
