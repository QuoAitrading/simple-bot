#!/usr/bin/env python3
"""
Test script to demonstrate the countdown and rainbow logo features
This simulates what happens when the user clicks "LAUNCH"
"""

import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from rainbow_logo import display_animated_logo


def simulate_countdown():
    """Simulate the 8-second countdown that appears in the GUI"""
    print("\n" + "=" * 60)
    print(" " * 15 + "🚀 LAUNCHING IN...")
    print("=" * 60)
    
    # Sample user settings
    settings = {
        "Broker": "TopStep",
        "Account": "50KTC-V2-398684 - $50,000.00",
        "Symbols": "ES, MES",
        "Contracts Per Trade": 3,
        "Daily Loss Limit": "$2,000",
        "Max Trades/Day": 10,
        "Confidence Threshold": "65%",
        "Shadow Mode": "OFF"
    }
    
    print("\n📋 Your Trading Configuration:")
    print("-" * 60)
    for key, value in settings.items():
        print(f"  {key}: {value}")
    print("-" * 60)
    
    # Countdown from 8 to 0
    for i in range(8, 0, -1):
        print(f"\n{'  ' * 10}{i}", flush=True)
        time.sleep(1)
    
    print(f"\n{'  ' * 10}0", flush=True)
    print("\n" + "=" * 60)
    print(" " * 10 + "✅ LAUNCHING BOT NOW!")
    print("=" * 60 + "\n")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print(" " * 10 + "QUOTRADING LAUNCHER TEST")
    print("=" * 60 + "\n")
    
    # Simulate the countdown that appears in the GUI
    simulate_countdown()
    
    # Wait a moment
    time.sleep(1)
    
    # Display the rainbow logo (this appears in PowerShell when bot starts)
    print("\n" + "=" * 60)
    print(" " * 5 + "PowerShell Terminal - Bot Starting...")
    print("=" * 60 + "\n")
    
    display_animated_logo(duration=8.0, fps=15)
    
    print("\n" + "=" * 60)
    print(" " * 15 + "✅ TEST COMPLETE!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
