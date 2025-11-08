"""
Simple Test API for Azure Container Apps
This verifies the deployment works before adding trading logic
"""
from fastapi import FastAPI
from datetime import datetime
import uvicorn

app = FastAPI(title="QuoTrading Signal Engine - Test")

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "QuoTrading Signal Engine",
        "version": "1.0-test",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/signal")
async def get_signal():
    """Test endpoint - will be replaced with real VWAP signals"""
    return {
        "signal": "NONE",
        "message": "Test mode - no real signals yet",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
