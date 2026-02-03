@echo off
chcp 65001 >nul
echo === Rectify Perspective - Installation ===

if not exist ".venv" (
    echo Création de l'environnement virtuel...
    python -m venv .venv
    if errorlevel 1 (
        echo ERREUR: Impossible de créer le venv. Vérifiez que Python 3.11+ est installé.
        pause
        exit /b 1
    )
)

echo Activation du venv...
call .venv\Scripts\activate.bat

echo Mise à jour de pip...
python -m pip install --upgrade pip

echo Installation des dépendances...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR: Échec de l'installation des dépendances.
    pause
    exit /b 1
)

echo.
echo Installation OK.
echo Lancez l'application avec: run.bat
pause
