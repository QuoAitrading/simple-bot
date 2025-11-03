#!/usr/bin/env python3
"""
VWAP Bounce Bot - Entry Point
Runs the bot from the reorganized src/ directory
"""

import sys
from pathlib import Path

# Add src/ to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run main
from main import main

if __name__ == "__main__":
    main()
