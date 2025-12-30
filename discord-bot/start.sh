#!/bin/bash
# Azure App Service startup script for Discord bot
pip install --upgrade pip
pip install -r requirements.txt
python -u ticket_bot.py
