@echo off
setlocal
cd /d "%~dp0.."

set TARGET_SCRIPT=%~1
if "%TARGET_SCRIPT%"=="" set TARGET_SCRIPT=main.py

:: 1. Check pythonw in PATH
where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw "%TARGET_SCRIPT%"
    exit /b 0
)

:: 2. Check py launcher
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" py -3w "%TARGET_SCRIPT%"
    exit /b 0
)

:: 3. Check Anaconda / Miniconda paths
if exist "%USERPROFILE%\anaconda3\pythonw.exe" (
    start "" "%USERPROFILE%\anaconda3\pythonw.exe" "%TARGET_SCRIPT%"
    exit /b 0
)
if exist "%USERPROFILE%\miniconda3\pythonw.exe" (
    start "" "%USERPROFILE%\miniconda3\pythonw.exe" "%TARGET_SCRIPT%"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "%TARGET_SCRIPT%"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%TARGET_SCRIPT%"
    exit /b 0
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
    start "" "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" "%TARGET_SCRIPT%"
    exit /b 0
)

:: 4. Fallback to normal python
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" python "%TARGET_SCRIPT%"
    exit /b 0
)

echo [ERROR] Python tidak ditemukan di sistem Anda!
echo Silakan install Python 3.10+ dari https://www.python.org atau Anaconda.
pause
exit /b 1
