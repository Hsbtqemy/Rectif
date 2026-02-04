@echo off
cd /d "%~dp0"

echo === Rectify Perspective - Installation ===
echo.

REM Python
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERREUR: Python introuvable. Installe Python 3.11+ depuis python.org
        pause
        exit /b 1
    )
    set PY=py -3
) else (
    set PY=python
)

REM Venv
if not exist ".venv\Scripts\python.exe" (
    echo Creation du venv...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo ERREUR: Impossible de creer le venv.
        pause
        exit /b 1
    )
)

REM Dependances
echo Installation des dependances...
.venv\Scripts\python.exe -m pip install --upgrade pip -q
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: Echec installation.
    pause
    exit /b 1
)

echo.
echo OK. Lance avec run.bat
pause
