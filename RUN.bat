@echo off
REM IT Equipment Inventory System - Auto Run Script
REM Just double-click this file to start everything!

echo.
echo =========================================
echo  IT Equipment Inventory System
echo =========================================
echo.

REM Check if we're in the right directory
if not exist "app.py" (
    echo [ERROR] app.py not found!
    echo.
    echo Make sure this file is in the same folder as app.py
    echo Current folder: %CD%
    echo.
    pause
    exit /b 1
)

echo [CHECK] Found app.py in current directory
echo Current folder: %CD%
echo.

REM Check if venv exists
if not exist "venv" (
    echo [INFO] Virtual environment not found
    echo [ACTION] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        echo Make sure Python is installed and added to PATH
        echo.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created
    echo.
)

echo [INFO] Setting up environment...
call venv\Scripts\activate.bat

echo [ACTION] Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    echo.
    pause
    exit /b 1
)
echo [SUCCESS] Dependencies installed
echo.

echo =========================================
echo [SUCCESS] Ready to start!
echo =========================================
echo.
echo Starting Flask application...
echo Open your browser to: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

pause
