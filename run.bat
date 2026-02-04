@echo off
setlocal EnableExtensions

REM Se placer dans le dossier du .bat
cd /d "%~dp0"

REM UTF-8 si dispo
chcp 65001 >nul 2>nul

set "VPY=%CD%\.venv\Scripts\python.exe"
set "VPYW=%CD%\.venv\Scripts\pythonw.exe"

if not exist "%VPY%" (
    echo ERREUR: Environnement virtuel absent. Lancez install.bat d'abord.
    pause
    exit /b 1
)

REM Choix du module d'entree (le plus probable)
set "ENTRY=rectify_gui"

REM Si pythonw existe, lancer sans console (sortie vers run.log pour debug)
if exist "%VPYW%" (
    start "" "%VPYW%" -m %ENTRY% 1>>"%CD%\run.log" 2>&1
    exit /b 0
) else (
    "%VPY%" -m %ENTRY%
    if errorlevel 1 (
        echo.
        echo ERREUR: L'application s'est terminee avec une erreur.
        pause
        exit /b 1
    )
)
