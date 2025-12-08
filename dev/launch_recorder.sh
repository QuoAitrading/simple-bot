#!/bin/bash
# ========================================
# QuoTrading Data Recorder Launcher
# ========================================
# This script opens a GUI window where you can:
# 1. Enter your broker credentials
# 2. Select symbols to record (ES, NQ, etc.)
# 3. Click START RECORDING button to begin
# 4. Click STOP RECORDING button when done
# 
# The GUI will appear after running this script!
# ========================================

echo "=========================================="
echo "QuoTrading Data Recorder"
echo "=========================================="
echo ""
echo "Opening GUI launcher..."
echo "Look for the window that will appear!"
echo ""
echo "Steps to use:"
echo "1. Enter your broker credentials"
echo "2. Select symbols to record"
echo "3. Click the START RECORDING button"
echo "4. Watch the status log for progress"
echo "5. Click STOP RECORDING when done"
echo ""
echo "=========================================="
echo ""

python3 DataRecorder_Launcher.py
