@echo off
title Fraclaw Stop
cd /d "%~dp0"

echo.
echo  =========================================
echo   FRACLAW - Chiusura Web App
echo  =========================================
echo.

:: Chiude le finestre per titolo (senza uccidere altri processi Python/Node)
echo [1/2] Chiusura Backend...
taskkill /FI "WINDOWTITLE eq Fraclaw - Backend*" /T /F > nul 2>&1

echo [2/2] Chiusura Frontend...
taskkill /FI "WINDOWTITLE eq Fraclaw - Frontend*" /T /F > nul 2>&1

:: Fallback: se le finestre erano già chiuse ma i processi girano in background
echo [*] Pulizia processi residui sulla porta 8000...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /PID %%a /F > nul 2>&1
)

echo [*] Pulizia processi residui sulla porta 5173...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173 "') do (
    taskkill /PID %%a /F > nul 2>&1
)

echo.
echo  Fraclaw fermato correttamente.
echo.
timeout /t 2 /nobreak > nul
