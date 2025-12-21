"""
Trade Copier API Endpoints
Add these to your Flask API to enable remote signal broadcasting

Usage:
    from copier_api import register_copier_routes
    register_copier_routes(app)
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Blueprint for copier routes
copier_bp = Blueprint('copier', __name__, url_prefix='/copier')

# In-memory storage (use Redis/DB in production for persistence)
connected_followers = {}  # follower_key -> {name, connected_at, last_heartbeat, copy_enabled, ...}
pending_signals = {}      # follower_key -> [list of pending signals]
master_keys = set()       # Valid master keys


def register_copier_routes(app, valid_master_keys=None):
    """
    Register copier routes with the Flask app
    
    Args:
        app: Flask application instance
        valid_master_keys: Set of valid master keys (optional - defaults to accepting any)
    """
    global master_keys
    if valid_master_keys:
        master_keys = set(valid_master_keys)
    app.register_blueprint(copier_bp)
    logger.info("📡 Trade Copier API endpoints registered")


@copier_bp.route('/broadcast', methods=['POST'])
def broadcast_signal():
    """
    Master broadcasts a signal to all connected followers
    
    Request:
        {
            "master_key": "your_master_key",
            "signal": {
                "signal_id": "abc123",
                "action": "OPEN",
                "symbol": "MES",
                "side": "BUY",
                "quantity": 1,
                "entry_price": 5000.00,
                ...
            }
        }
    
    Response:
        {"received_count": 3}
    """
    data = request.get_json()
    master_key = data.get('master_key')
    signal = data.get('signal')
    
    if not master_key or not signal:
        return jsonify({"error": "Missing master_key or signal"}), 400
    
    # Validate master key if we have a whitelist
    if master_keys and master_key not in master_keys:
        return jsonify({"error": "Invalid master key"}), 403
    
    # Add signal to all connected followers' queues
    received_count = 0
    for follower_key, follower in connected_followers.items():
        if follower.get('copy_enabled', True):
            if follower_key not in pending_signals:
                pending_signals[follower_key] = []
            pending_signals[follower_key].append(signal)
            received_count += 1
    
    logger.info(f"📤 Signal broadcast: {signal.get('action')} {signal.get('side')} {signal.get('quantity')} {signal.get('symbol')} → {received_count} followers")
    
    return jsonify({"received_count": received_count})


@copier_bp.route('/register', methods=['POST'])
def register_follower():
    """
    Follower registers with the relay server
    
    Request:
        {
            "follower_key": "unique_key",
            "follower_name": "My Account",
            "account_ids": ["123", "456"],
            "device_fingerprint": "abc123"
        }
    """
    data = request.get_json()
    follower_key = data.get('follower_key')
    follower_name = data.get('follower_name', 'Unknown')
    account_ids = data.get('account_ids', [])
    device_fingerprint = data.get('device_fingerprint', '')
    
    if not follower_key:
        return jsonify({"error": "Missing follower_key"}), 400
    
    now = datetime.now(timezone.utc).isoformat()
    
    connected_followers[follower_key] = {
        'name': follower_name,
        'account_ids': account_ids,
        'device_fingerprint': device_fingerprint,
        'connected_at': now,
        'last_heartbeat': now,
        'copy_enabled': True,
        'signals_received': 0,
        'signals_executed': 0
    }
    
    # Initialize signal queue
    if follower_key not in pending_signals:
        pending_signals[follower_key] = []
    
    logger.info(f"✅ Follower registered: {follower_name} ({follower_key[:8]}...) - {len(account_ids)} accounts")
    
    return jsonify({"status": "registered", "follower_key": follower_key})


@copier_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Follower sends heartbeat to stay connected"""
    data = request.get_json()
    follower_key = data.get('follower_key')
    
    if follower_key in connected_followers:
        connected_followers[follower_key]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        return jsonify({"status": "ok"})
    
    return jsonify({"error": "Not registered"}), 401


@copier_bp.route('/unregister', methods=['POST'])
def unregister_follower():
    """Follower disconnects from relay server"""
    data = request.get_json()
    follower_key = data.get('follower_key')
    
    if follower_key in connected_followers:
        name = connected_followers[follower_key].get('name', 'Unknown')
        del connected_followers[follower_key]
        if follower_key in pending_signals:
            del pending_signals[follower_key]
        logger.info(f"🔌 Follower unregistered: {name}")
    
    return jsonify({"status": "unregistered"})


@copier_bp.route('/poll', methods=['GET'])
def poll_signals():
    """
    Follower polls for new signals (long-polling)
    
    Returns next pending signal, or 204 if none
    """
    follower_key = request.args.get('follower_key')
    
    if not follower_key or follower_key not in connected_followers:
        return jsonify({"error": "Not registered"}), 401
    
    # Update heartbeat
    connected_followers[follower_key]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
    
    # Check for pending signals
    if follower_key in pending_signals and pending_signals[follower_key]:
        signal = pending_signals[follower_key].pop(0)
        connected_followers[follower_key]['signals_received'] = \
            connected_followers[follower_key].get('signals_received', 0) + 1
        return jsonify({"signal": signal})
    
    # No signals - return 204 (no content)
    return '', 204


@copier_bp.route('/report', methods=['POST'])
def report_execution():
    """Follower reports successful signal execution"""
    data = request.get_json()
    follower_key = data.get('follower_key')
    signal_id = data.get('signal_id')
    status = data.get('status')
    
    if follower_key in connected_followers and status == 'executed':
        connected_followers[follower_key]['signals_executed'] = \
            connected_followers[follower_key].get('signals_executed', 0) + 1
    
    return jsonify({"status": "reported"})


@copier_bp.route('/followers', methods=['GET'])
def get_followers():
    """Get list of connected followers (for master dashboard)"""
    master_key = request.args.get('master_key')
    
    # Optional: validate master key
    if master_keys and master_key not in master_keys:
        return jsonify({"error": "Invalid master key"}), 403
    
    followers = []
    for follower_key, follower in connected_followers.items():
        followers.append({
            'client_id': follower_key,
            'name': follower['name'],
            'account_ids': follower.get('account_ids', []),
            'connected_at': follower['connected_at'],
            'last_heartbeat': follower['last_heartbeat'],
            'copy_enabled': follower.get('copy_enabled', True),
            'signals_received': follower.get('signals_received', 0),
            'signals_executed': follower.get('signals_executed', 0)
        })
    
    return jsonify({"followers": followers})


@copier_bp.route('/toggle_follower', methods=['POST'])
def toggle_follower_copy():
    """Toggle copy on/off for a specific follower"""
    data = request.get_json()
    master_key = data.get('master_key')
    follower_key = data.get('follower_key')
    
    if master_keys and master_key not in master_keys:
        return jsonify({"error": "Invalid master key"}), 403
    
    if follower_key in connected_followers:
        connected_followers[follower_key]['copy_enabled'] = \
            not connected_followers[follower_key].get('copy_enabled', True)
        return jsonify({
            "follower_key": follower_key,
            "copy_enabled": connected_followers[follower_key]['copy_enabled']
        })
    
    return jsonify({"error": "Follower not found"}), 404


@copier_bp.route('/status', methods=['GET'])
def copier_status():
    """Get overall copier system status"""
    return jsonify({
        "active_followers": len(connected_followers),
        "total_pending_signals": sum(len(s) for s in pending_signals.values()),
        "server_time": datetime.now(timezone.utc).isoformat()
    })
