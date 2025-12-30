# Discord Bot Deployment Guide

## Azure Deployment

### Prerequisites
1. Azure CLI installed
2. Azure account with permissions to create App Services
3. Bot token from Discord Developer Portal
4. `config.json` file with your bot token (for local testing)

### Deployment Steps

1. **Prepare Configuration**
   ```bash
   # Create config.json (only for local testing - NOT committed to git)
   {
     "bot_token": "your_discord_bot_token_here"
   }
   ```

2. **Deploy to Azure**
   ```powershell
   # Run the deployment script
   .\deploy-azure.ps1
   ```

   The script will:
   - Login to Azure (if needed)
   - Create/update the Web App
   - Set the bot token as environment variable `DISCORD_BOT_TOKEN`
   - Configure startup command
   - Enable "Always On" to prevent sleeping

3. **Verify Deployment**
   - Check health endpoint: `https://quotrading-discord-bot.azurewebsites.net/health`
   - View logs: `az webapp log tail --name quotrading-discord-bot --resource-group quotrading-rg`

### Environment Variables (Azure)

Set these in Azure App Service Configuration:
- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)
- `API_URL` - Flask API URL (default: https://quotrading-flask-api.azurewebsites.net)
- `PORT` - HTTP port (automatically set by Azure)

### Features

1. **Ticket System**
   - Create tickets via button
   - Close tickets (ticket owner or staff only)
   - Track active tickets

2. **Server Health Monitoring**
   - Updates status channel every 5 minutes
   - Shows 🟢 when API is healthy, 🔴 when issues detected
   - Displays last check time

3. **Welcome Messages**
   - Rainbow divider GIF
   - Custom emojis (pepe_dance, black_hole)
   - Member count with ordinal suffix

4. **Leveling System**
   - XP gain on messages (15-25 XP)
   - 1 minute cooldown between XP gains
   - 10 levels with custom titles
   - Role assignment on level up

### Heartbeat Schedule

- **Discord Bot Heartbeat**: Every 5 minutes (300 seconds)
  - Sends heartbeat to Flask API at `/api/discord/heartbeat`
  - Reports server count and active tickets
  
- **Status Channel Update**: Every 5 minutes (300 seconds)
  - Checks API health
  - Updates status message
  - Updates channel emoji (🟢/🔴)

### Troubleshooting

**Bot not starting:**
1. Check logs: `az webapp log tail --name quotrading-discord-bot --resource-group quotrading-rg`
2. Verify `DISCORD_BOT_TOKEN` is set in Azure configuration
3. Check Python version is 3.11 (set in deploy script)
4. Ensure `Always On` is enabled

**Tickets not working:**
1. Verify bot has proper permissions in Discord server
2. Check bot can create channels and manage permissions
3. Ensure persistent views are registered (happens on bot ready)

**Status channel not updating:**
1. Verify `status_config.json` exists with valid channel_id and message_id
2. Run `setup_status.py` to create the status channel if needed
3. Check API_URL is reachable from Azure

**Heartbeat not showing in API:**
1. Verify API URL is correct (check environment variable)
2. Test endpoint: `curl -X POST https://quotrading-flask-api.azurewebsites.net/api/discord/heartbeat -H "Content-Type: application/json" -d '{"servers":1,"active_tickets":0}'`
3. Check admin dashboard: `https://quotrading-flask-api.azurewebsites.net/api/admin/discord-status?admin_key=YOUR_ADMIN_KEY`

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export DISCORD_BOT_TOKEN="your_token_here"

# Run bot
python ticket_bot.py
```

The bot will start an HTTP server on port 8000 (or PORT environment variable) for Azure health checks.

### Azure App Service Configuration

- **Runtime**: Python 3.11
- **Startup Command**: Configured via `start.sh`
- **Always On**: Enabled (prevents app from sleeping)
- **App Service Plan**: B1 Basic (minimum recommended)
- **Region**: East US (or as configured)

### Security Notes

1. Never commit `config.json` with real tokens (already in .gitignore)
2. Use Azure environment variables for sensitive data
3. Bot token is stored securely in Azure App Service Configuration
4. API communication uses HTTPS only
