@echo off
title Fraclaw Mobile App - Windows Test
cd /d "%~dp0"

echo.
echo  =========================================
echo   FRACLAW - Flutter Windows Tester
echo  =========================================
echo.

:: Check if flutter is in path
where flutter >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Flutter SDK not found in PATH.
    echo Please make sure Flutter is installed and added to your system environment variables.
    pause
    exit /b 1
)

echo [PROCESS] Launching lib\main.dart on Windows...
echo [INFO] Make sure your backend is running (use start_backend.bat first)
echo.

:: Run flutter
flutter run -d windows

pause
