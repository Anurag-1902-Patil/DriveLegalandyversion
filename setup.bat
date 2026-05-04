@echo off
title DriveLegal Setup
color 0A

echo.
echo ============================================
echo     DriveLegal - Auto Setup Script
echo ============================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11 from https://python.org
    pause
    exit /b
)

echo [1/6] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b
)

echo [2/6] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/6] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed. Check requirements.txt
    pause
    exit /b
)

echo [4/6] Setting up .env file...
if not exist .env (
    copy .env.example .env
    echo.
    echo [ACTION REQUIRED] Open .env and add your ZHIPUAI_API_KEY
    echo Press any key once you have saved your API key...
    notepad .env
    pause
) else (
    echo .env already exists, skipping...
)

echo [5/6] Preprocessing raw data...
python scripts\preprocess.py
if errorlevel 1 (
    echo [ERROR] Preprocess failed. Make sure data\raw\ has .txt files.
    pause
    exit /b
)

echo [6/6] Building FAISS index (downloads ~80MB model first time)...
python scripts\embed.py
if errorlevel 1 (
    echo [ERROR] Embedding failed.
    pause
    exit /b
)

echo.
echo ============================================
echo     Setup Complete!
echo ============================================
echo.
echo Run start.bat to launch DriveLegal.
echo.
pause
