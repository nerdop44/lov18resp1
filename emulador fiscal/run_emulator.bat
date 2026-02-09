@echo off
title Emulador Impresora Fiscal Runner

echo Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no encontrado en el PATH.
    echo Por favor instale Python desde https://www.python.org/
    pause
    exit /b
)

echo Verificando Tkinter...
python -c "import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] La libreria Tkinter no esta instalada.
    echo En Windows, Tkinter suele venir con la instalacion de Python.
    echo Por favor repare su instalacion de Python y asegurese de marcar "tcl/tk and IDLE".
    pause
    exit /b
)

echo Iniciando Emulador...
python pyfiscal_emulator.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] El emulador se cerro con un error.
    pause
)
