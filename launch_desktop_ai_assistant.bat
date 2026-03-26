@echo off
setlocal
cd /d "%~dp0"

set "PYTHON312="
set "PYTHON_URL=https://www.python.org/downloads/windows/"

where py >nul 2>nul
if not errorlevel 1 (
    for /f "usebackq delims=" %%I in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON312=%%I"
)

if not defined PYTHON312 (
    for /f "usebackq delims=" %%I in (`python -c "import sys; print(sys.executable if sys.version_info[:2] == (3, 12) else '')" 2^>nul`) do set "PYTHON312=%%I"
)

if not defined PYTHON312 goto :missing_python

echo Using Python 3.12 at:
echo %PYTHON312%
echo.

set "NEED_INSTALL="

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    "%PYTHON312%" -m venv venv
    if errorlevel 1 goto :install_failed
    set "NEED_INSTALL=1"
)

if not exist "venv\.requirements_installed" set "NEED_INSTALL=1"
if exist "venv\.requirements_installed" if requirements.txt GTR "venv\.requirements_installed" set "NEED_INSTALL=1"

if defined NEED_INSTALL (
    echo Installing requirements...
    "venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :install_failed

    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :install_failed

    copy /y requirements.txt "venv\.requirements_installed" >nul
) else (
    echo Requirements already installed.
)

echo Launching Desktop AI Assistant...
"venv\Scripts\python.exe" main.py
exit /b %errorlevel%

:missing_python
set "PS_TEMP=%TEMP%\desktop_ai_python_notice_%RANDOM%.ps1"
> "%PS_TEMP%" (
    echo Add-Type -AssemblyName System.Windows.Forms
    echo Add-Type -AssemblyName System.Drawing
    echo $url = '%PYTHON_URL%'
    echo $form = New-Object Windows.Forms.Form
    echo $form.Text = 'Python 3.12 Required'
    echo $form.Size = New-Object Drawing.Size(500,190)
    echo $form.StartPosition = 'CenterScreen'
    echo $form.TopMost = $true
    echo $form.FormBorderStyle = 'FixedDialog'
    echo $form.MaximizeBox = $false
    echo $form.MinimizeBox = $false
    echo $label = New-Object Windows.Forms.Label
    echo $label.Text = 'Desktop AI Assistant needs Python 3.12 before it can set up the virtual environment and launch the app.'
    echo $label.Location = New-Object Drawing.Point(20,20)
    echo $label.Size = New-Object Drawing.Size(440,45)
    echo $label.Font = New-Object Drawing.Font('Segoe UI',10)
    echo $form.Controls.Add($label)
    echo $link = New-Object Windows.Forms.LinkLabel
    echo $link.Text = $url
    echo $link.Location = New-Object Drawing.Point(20,80)
    echo $link.Size = New-Object Drawing.Size(430,24)
    echo $link.Font = New-Object Drawing.Font('Segoe UI',10)
    echo $link.add_Click({ Start-Process $url })
    echo $form.Controls.Add($link)
    echo $button = New-Object Windows.Forms.Button
    echo $button.Text = 'Open Download Page'
    echo $button.Location = New-Object Drawing.Point(20,115)
    echo $button.Size = New-Object Drawing.Size(160,30)
    echo $button.add_Click({ Start-Process $url; $form.Close() })
    echo $form.Controls.Add($button)
    echo [void]$form.ShowDialog()
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_TEMP%"
del "%PS_TEMP%" >nul 2>nul
exit /b 1

:install_failed
echo.
echo Setup failed. Please review the message above and try again.
pause
exit /b 1
