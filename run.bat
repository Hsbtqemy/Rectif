@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERREUR: Environnement virtuel absent. Exécutez install.bat d'abord.
    pause
    exit /b 1
)

REM pythonw = lancement sans fenêtre console (terminal dissimulé)
start "" ".venv\Scripts\pythonw.exe" -m rectify_gui
