@echo off
setlocal
cd /d "%~dp0"

:: 1. Check python in PATH
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python "agy_switcher.py"
    exit /b 0
)

:: 2. Check py launcher
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -3 "agy_switcher.py"
    exit /b 0
)

:: 3. Check Anaconda / Miniconda paths
if exist "%USERPROFILE%\anaconda3\python.exe" (
    "%USERPROFILE%\anaconda3\python.exe" "agy_switcher.py"
    exit /b 0
)
if exist "%USERPROFILE%\miniconda3\python.exe" (
    "%USERPROFILE%\miniconda3\python.exe" "agy_switcher.py"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "agy_switcher.py"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "agy_switcher.py"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" "agy_switcher.py"
    exit /b 0
)

echo [ERROR] Python tidak ditemukan di sistem Anda!
echo Silakan install Python 3.10+ dari https://www.python.org atau Anaconda.
pause
exit /b 1
