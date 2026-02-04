@echo off
REM Lance install.bat en gardant la fenetre ouverte (pour voir les erreurs)
cd /d "%~dp0"
cmd /k "install.bat --debug"
