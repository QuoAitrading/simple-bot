"""
Minimal Azure startup - starts HTTP server immediately, bot in background.
"""
import os
import sys
import threading
import asyncio
from aiohttp import web

# Health check endpoint
async def health(request):
    return web.json_response({"status": "ok"})

async def home(request):
    return web.Response(text="QuoTrading Bot")

def start_bot():
    """Start the Discord bot in background."""
    import ticket_bot
    asyncio.set_event_loop(asyncio.new_event_loop())
    ticket_bot.bot.run(ticket_bot.TOKEN)

if __name__ == '__main__':
    # Start bot thread FIRST (non-blocking)
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    print("Bot thread started")
    
    # Start web server (blocking) - Azure needs this
    app = web.Application()
    app.router.add_get('/', home)
    app.router.add_get('/health', health)
    
    port = int(os.environ.get('PORT', 8000))
    print(f"Starting HTTP on port {port}")
    web.run_app(app, host='0.0.0.0', port=port)
