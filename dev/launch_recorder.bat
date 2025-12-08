@echo off
REM ========================================
REM QuoTrading Data Recorder Launcher
REM ========================================
REM This script opens a GUI window where you can:
REM 1. Enter your broker credentials
REM 2. Select symbols to record (ES, NQ, etc.)
REM 3. Click START RECORDING button to begin
REM 4. Click STOP RECORDING button when done
REM 
REM The GUI will appear after running this script!
REM ========================================

echo ==========================================
echo QuoTrading Data Recorder
echo ==========================================
echo.
echo Opening GUI launcher...
echo Look for the window that will appear!
echo.
echo Steps to use:
echo 1. Enter your broker credentials
echo 2. Select symbols to record
echo 3. Click the START RECORDING button
echo 4. Watch the status log for progress
echo 5. Click STOP RECORDING when done
echo.
echo ==========================================
echo.

python DataRecorder_Launcher.py
pause
