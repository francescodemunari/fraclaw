@echo off
title Fraclaw Launcher
cd /d "%~dp0"

echo.
echo  =========================================
echo   FRACLAW - Avvio Web App
echo  =========================================
echo.

:: Verifica che il venv esista
if not exist ".venv\Scripts\python.exe" (
    echo [ERRORE] Ambiente virtuale non trovato.
    echo Assicurati di aver eseguito: py -3.12 -m venv .venv
    pause
    exit /b 1
)

:: Avvio Backend in una finestra separata
echo [1/2] Avvio Backend (porta 8000)...
start "Fraclaw - Backend" cmd /k ".venv\Scripts\python.exe src\web\api.py"

:: Breve pausa per dare tempo al backend di inizializzarsi
timeout /t 3 /nobreak > nul

:: Avvio Frontend in una finestra separata
echo [2/2] Avvio Frontend (porta 5173)...
start "Fraclaw - Frontend" cmd /k "cd webapp && npm run dev"

echo.
echo  =========================================
echo   Fraclaw in avvio!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo  =========================================
echo.
echo  Per chiudere tutto, esegui: stop_webapp.bat
echo.
timeout /t 3 /nobreak > nul
