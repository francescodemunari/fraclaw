@echo off
title Fraclaw Mobile Backend
cd /d "%~dp0"

echo.
echo  =========================================
echo   FRACLAW - Mobile App Backend
echo  =========================================
echo.

:: Verify venv exists in parent directory
if not exist "..\.venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in ..\.venv
    echo Please make sure you have the .venv folder in the project root.
    pause
    exit /b 1
)

echo [PROCESS] Starting Backend on http://0.0.0.0:8000...
echo [INFO] Press Ctrl+C to stop the server.
echo.

:: Run the backend from parent directory context
"..\.venv\Scripts\python.exe" ..\src\web\api.py

pause
