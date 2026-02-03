@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo ERREUR: Environnement virtuel absent. Exécutez install.bat d'abord.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m rectify_gui
if errorlevel 1 (
    echo.
    echo Une erreur s'est produite.
    pause
    exit /b 1
)
