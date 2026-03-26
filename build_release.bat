@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Ensuring virtual environment exists...
if not exist "venv\Scripts\python.exe" (
    py -3.12 -m venv venv || goto :fail
)

echo [2/4] Installing build dependencies...
call "venv\Scripts\activate.bat" || goto :fail
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt || goto :fail

echo [3/4] Building Desktop AI Assistant...
python -m PyInstaller --noconfirm --clean desktop_ai_assistant.spec || goto :fail

echo [4/4] Build finished.
if not exist "release" mkdir release
copy /Y "dist\DesktopAIAssistant.exe" "release\DesktopAIAssistant.exe" >nul || goto :fail
echo Release EXE: %cd%\release\DesktopAIAssistant.exe
endlocal
exit /b 0

:fail
echo Build failed.
endlocal
exit /b 1
