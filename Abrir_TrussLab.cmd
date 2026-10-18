@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Ejecuta primero Instalar.ps1 para preparar el entorno.
  pause
  exit /b 1
)
start "TrussLab 3D" ".venv\Scripts\pythonw.exe" "run.py"
