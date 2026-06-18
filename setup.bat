@echo off
REM IT Equipment Inventory System - Windows Setup Script

echo.
echo ==========================================
echo IT Equipment Inventory System Setup
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://www.python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [✓] Python found: 
python --version
echo.

REM Create virtual environment
if not exist "venv" (
    echo [*] Creating virtual environment...
    python -m venv venv
    echo [✓] Virtual environment created
) else (
    echo [✓] Virtual environment already exists
)

echo.

REM Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

echo.

REM Install dependencies
echo [*] Installing dependencies...
pip install -r requirements.txt -q
echo [✓] Dependencies installed

echo.

REM Create directories
echo [*] Creating directories...
if not exist "templates" mkdir templates
if not exist "static" mkdir static
echo [✓] Directories created

echo.

REM Display next steps
echo ==========================================
echo [✓] Setup Complete!
echo ==========================================
echo.
echo To start the application, run:
echo   python app.py
echo.
echo Then open your browser to:
echo   http://localhost:5000
echo.
echo To install as PWA:
echo   1. Open the app in your browser
echo   2. Look for the 'Install App' button
echo   3. Click to install on your device
echo.
echo For more information, see README.md
echo.
pause
