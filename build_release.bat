@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Ensuring virtual environment exists...
if not exist "venv\Scripts\python.exe" (
    py -3.12 -m venv venv
)

echo [2/4] Installing build dependencies...
call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [3/4] Building Desktop AI Assistant...
python -m PyInstaller --noconfirm --clean desktop_ai_assistant.spec

echo [4/4] Build finished.
if not exist "release" mkdir release
copy /Y "dist\DesktopAIAssistant.exe" "release\DesktopAIAssistant.exe" >nul
echo Release EXE: %cd%\release\DesktopAIAssistant.exe
endlocal
