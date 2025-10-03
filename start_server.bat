@echo off
REM Start the Inspector web server on Windows

REM Change to the script's directory
cd /d "%~dp0"

REM Pull latest updates from git
echo Checking for updates...
git pull

REM Check if virtual environment exists, if not create it
IF NOT EXIST "venv" (
    echo Creating virtual environment...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo Error: Failed to create virtual environment.
        echo Make sure Python is installed and added to PATH.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat
IF ERRORLEVEL 1 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
IF ERRORLEVEL 1 (
    echo Installing dependencies...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    IF ERRORLEVEL 1 (
        echo Error: Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Run the server
echo.
echo Starting Inspector web server...
echo Visit http://localhost:8000 in your browser
echo.
python server.py

