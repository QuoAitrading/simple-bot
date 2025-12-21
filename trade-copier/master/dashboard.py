"""
Master Dashboard - Flask web UI for the Master system
Shows connected followers, positions, and signal controls
Runs at localhost:3000
"""

from flask import Flask, render_template, jsonify, request
import logging
import os

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global state (set by main.py when starting)
master_state = {
    "broadcaster": None,
    "broker": None,
    "copy_enabled": True,
    "connected_followers": [],
    "signal_history": [],
    "positions": {}
}


def set_master_state(broadcaster, broker):
    """Called by main.py to set the broadcaster and broker instances"""
    master_state["broadcaster"] = broadcaster
    master_state["broker"] = broker


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current master status"""
    broadcaster = master_state["broadcaster"]
    broker = master_state["broker"]
    
    status = {
        "copy_enabled": master_state["copy_enabled"],
        "connected": broker.connected if broker else False,
        "account_balance": broker.account_balance if broker else 0,
        "positions": broker.positions if broker else {},
        "followers": [],
        "total_signals": 0
    }
    
    if broadcaster:
        bcast_status = broadcaster.get_status()
        status["followers"] = bcast_status["followers"]
        status["total_signals"] = bcast_status["total_signals_sent"]
    
    return jsonify(status)


@app.route('/api/followers')
def get_followers():
    """Get list of connected followers"""
    broadcaster = master_state["broadcaster"]
    if broadcaster:
        return jsonify({"followers": broadcaster.get_status()["followers"]})
    return jsonify({"followers": []})


@app.route('/api/toggle_copy', methods=['POST'])
def toggle_copy():
    """Toggle copy on/off globally"""
    master_state["copy_enabled"] = not master_state["copy_enabled"]
    status = "ENABLED" if master_state["copy_enabled"] else "DISABLED"
    logger.info(f"📋 Copy {status}")
    return jsonify({"copy_enabled": master_state["copy_enabled"]})


@app.route('/api/flatten_all', methods=['POST'])
def flatten_all():
    """Emergency flatten all positions"""
    broadcaster = master_state["broadcaster"]
    broker = master_state["broker"]
    
    if broker and broadcaster:
        # Flatten master first
        # Then broadcast flatten to all followers
        import asyncio
        asyncio.run(broadcaster.broadcast_flatten("ALL"))
        logger.warning("🚨 FLATTEN ALL sent to all followers")
        return jsonify({"status": "flatten_sent"})
    
    return jsonify({"error": "Not connected"}), 400


@app.route('/api/signal_history')
def get_signal_history():
    """Get recent signal history"""
    broadcaster = master_state["broadcaster"]
    if broadcaster:
        history = [s.to_dict() for s in broadcaster.signal_history[-50:]]
        return jsonify({"signals": history})
    return jsonify({"signals": []})


def run_dashboard(port: int = 3000):
    """Start the dashboard server"""
    logger.info(f"🖥️  Master Dashboard starting at http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
