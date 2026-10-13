@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
findstr /C:SET_DISCORD_APPLICATION_ID app.py >nul
if not errorlevel 1 (
  echo Configure the project Discord Application ID in app.py before building.
  exit /b 2
)
py -m PyInstaller --noconfirm --clean --onefile --windowed --name DotaActivity --icon assets\logo_dota.ico --add-data "assets\logo_dota.png;assets" --collect-all pypresence app.py
if errorlevel 1 exit /b 1
echo.
echo Ready: dist\DotaActivity.exe
pause
