@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  if errorlevel 1 goto :error
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
.venv\Scripts\python.exe app.py
pause
exit /b 0
:error
echo Could not prepare the beta. Check that Python and an internet connection are available.
pause
exit /b 1
