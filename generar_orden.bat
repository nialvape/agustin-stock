@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === git fetch ===
git fetch
if errorlevel 1 (
  echo [ERROR] git fetch
  pause
  exit /b 1
)

echo === git pull ===
git pull
if errorlevel 1 (
  echo [ERROR] git pull
  pause
  exit /b 1
)

echo === pip install -r requirements.txt ===
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install
  pause
  exit /b 1
)

echo === generar_orden.py (lee config.txt) ===
python generar_orden.py
if errorlevel 1 (
  echo [ERROR] generar_orden.py
  pause
  exit /b 1
)

echo.
echo Listo.
pause
endlocal
