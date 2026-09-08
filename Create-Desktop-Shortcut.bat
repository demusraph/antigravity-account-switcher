@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Antigravity Control Center - Shortcut Installer
echo ===================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$sh = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$shortcut = $sh.CreateShortcut(\"$desktop\Antigravity Control Center.lnk\"); " ^
    "$shortcut.TargetPath = \"%~dp0Launch-GUI.bat\"; " ^
    "$shortcut.WorkingDirectory = \"%~dp0\"; " ^
    "$shortcut.IconLocation = \"%~dp0app_icon.ico,0\"; " ^
    "$shortcut.Description = 'Antigravity Multi-Account Controller'; " ^
    "$shortcut.WindowStyle = 7; " ^
    "$shortcut.Save(); " ^
    "Write-Host '[SUCCESS] Shortcut created on Desktop!' -ForegroundColor Green; " ^
    "Write-Host 'You can now double-click \"Antigravity Control Center\" on your Desktop.' -ForegroundColor Cyan"

echo.
pause
