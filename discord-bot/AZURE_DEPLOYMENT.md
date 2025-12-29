# Discord Bot Azure Deployment

## Quick Start

The Discord bot is ready for Azure deployment with proper health check support.

### Deploy to Azure

```powershell
cd discord-bot
.\deploy-azure.ps1
```

Or manually:
```bash
cd discord-bot

# Deploy to Azure App Service
az webapp up \
    --resource-group quotrading-rg \
    --name quotrading-discord-bot \
    --runtime "PYTHON:3.12" \
    --sku B1

# Set environment variables
az webapp config appsettings set \
    --resource-group quotrading-rg \
    --name quotrading-discord-bot \
    --settings DISCORD_BOT_TOKEN="your_token_here" \
              API_URL="https://quotrading-flask-api.azurewebsites.net"

# Set startup command
az webapp config set \
    --resource-group quotrading-rg \
    --name quotrading-discord-bot \
    --startup-file "python ticket_bot.py"
```

## Required Environment Variables

Set in Azure Portal > Configuration > Application Settings:

- **DISCORD_BOT_TOKEN** (Required) - Your Discord bot token from Discord Developer Portal
- **API_URL** (Optional) - Flask API URL for heartbeat reporting (default: https://quotrading-flask-api.azurewebsites.net)
- **PORT** (Auto-set by Azure) - HTTP server port (default: 8000)

## Features

1. **Ticket System** - Create support tickets with buttons
2. **Health Check** - HTTP endpoint for Azure monitoring at `/health`
3. **Heartbeat Reporting** - Reports status to Flask API every 60 seconds
4. **Persistent Views** - Buttons work after bot restart

## Files

- `ticket_bot.py` - Production bot with HTTP server (use for Azure)
- `bot.py` - Simplified version (development/testing)
- `deploy-azure.ps1` - PowerShell deployment script

## Verify Deployment

After deployment:

1. **Health Check**: `https://quotrading-discord-bot.azurewebsites.net/health`
2. **Bot Status**: Check Discord server - bot should be online
3. **Logs**: `az webapp log tail --name quotrading-discord-bot --resource-group quotrading-rg`

## Troubleshooting

### Bot not starting
- Verify DISCORD_BOT_TOKEN is set correctly
- Check logs for errors
- Ensure Python 3.12 runtime is selected

### Buttons not working
- Persistent views are registered on bot startup
- Restart bot if buttons become unresponsive
- Check bot has proper permissions in Discord server

### Health check fails
- Verify HTTP server is running on correct PORT
- Check Azure allows HTTP traffic
- Review application logs

## Discord Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create or select your application
3. Go to Bot section
4. Copy bot token and set as DISCORD_BOT_TOKEN
5. Enable required intents:
   - Server Members Intent
   - Message Content Intent
6. Invite bot to your server with required permissions:
   - Manage Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Manage Messages

## Monitoring

View logs in real-time:
```bash
az webapp log tail --name quotrading-discord-bot --resource-group quotrading-rg
```

Download logs:
```bash
az webapp log download --name quotrading-discord-bot --resource-group quotrading-rg
```

## Support

For issues:
1. Check Azure Portal diagnostics
2. Review bot logs
3. Test health endpoint
4. Verify Discord token is valid
5. Contact: support@quotrading.com
