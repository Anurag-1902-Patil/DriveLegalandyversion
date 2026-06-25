@echo off
REM ============================================================================
REM DriveLegal – GPS Setup Script
REM Run this ONCE to install the offline geocoder and verify dependencies.
REM ============================================================================

echo.
echo  ======================================================
echo   DriveLegal — GPS Integration Setup
echo  ======================================================
echo.

REM --- 1. Activate virtualenv if present ---
if exist "venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [1/4] No venv found — using system Python.
)

REM --- 2. Install / verify reverse_geocoder ---
echo.
echo [2/4] Installing offline geocoder (reverse_geocoder)...
pip install reverse_geocoder==1.5.1
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: pip install failed. Please check your Python environment.
    pause
    exit /b 1
)
echo  reverse_geocoder installed successfully.

REM --- 3. Verify Ollama is running ---
echo.
echo [3/4] Checking Ollama connection...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  Ollama is running.
) else (
    echo  WARNING: Ollama not detected on localhost:11434
    echo  Make sure to run:  ollama serve
    echo  And pull model:    ollama pull mistral
)

REM --- 4. Quick offline geocoder test (Pune coords) ---
echo.
echo [4/4] Testing offline reverse geocoder (Pune, India)...
python -c "from geocoding.offline_geocoder import resolve; r = resolve(18.5204, 73.8567); print('  Result:', r.city, r.state, r.country) if r else print('  FAIL: geocoder returned None')"
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Geocoder test failed. Check that reverse_geocoder is installed.
    pause
    exit /b 1
)

echo.
echo  ======================================================
echo   GPS setup complete! 
echo.
echo   Start the server:   uvicorn app.main:app --reload
echo   Open in browser:    http://localhost:8000/ui
echo   API docs:           http://localhost:8000/docs
echo  ======================================================
echo.
pause
