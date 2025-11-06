"""
QuoTrading Cloud Validation Server
====================================
Flask API server for validating user credentials.

This server provides a simple authentication endpoint that validates
username, password, and API key combinations against a user database.

Endpoints:
- POST /api/validate - Validate user credentials

Usage:
    python validation_server.py

Configuration:
- Update USER_DATABASE with your actual user credentials
- Modify host/port as needed for production deployment
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import hashlib

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# User database (In production, use a real database)
# Format: username -> {password_hash, api_key, user_data}
USER_DATABASE = {
    "demo_user": {
        "password": hashlib.sha256("demo_password".encode()).hexdigest(),
        "api_key": "DEMO_API_KEY_12345",
        "user_data": {
            "email": "demo@quotrading.com",
            "account_type": "premium",
            "active": True
        }
    },
    "test_trader": {
        "password": hashlib.sha256("test123".encode()).hexdigest(),
        "api_key": "TEST_API_KEY_67890",
        "user_data": {
            "email": "test@quotrading.com",
            "account_type": "basic",
            "active": True
        }
    }
}


def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


@app.route('/api/validate', methods=['POST'])
def validate_credentials():
    """
    Validate user credentials.
    
    Request JSON:
    {
        "username": "string",
        "password": "string",
        "api_key": "string"
    }
    
    Response JSON:
    {
        "valid": true/false,
        "message": "string",
        "user_data": {...}  // Only included if valid
    }
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            logger.warning("Empty request received")
            return jsonify({
                "valid": False,
                "message": "No data provided"
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        api_key = data.get('api_key', '').strip()
        
        # Log the validation attempt
        logger.info(f"Validation attempt for user: {username}")
        
        # Validate required fields
        if not username or not password or not api_key:
            logger.warning(f"Missing fields in request from user: {username}")
            return jsonify({
                "valid": False,
                "message": "All fields are required"
            }), 400
        
        # Check if user exists
        if username not in USER_DATABASE:
            logger.warning(f"User not found: {username}")
            return jsonify({
                "valid": False,
                "message": "Invalid username or password"
            }), 200
        
        user = USER_DATABASE[username]
        
        # Validate password
        password_hash = hash_password(password)
        if password_hash != user['password']:
            logger.warning(f"Invalid password for user: {username}")
            return jsonify({
                "valid": False,
                "message": "Invalid username or password"
            }), 200
        
        # Validate API key
        if api_key != user['api_key']:
            logger.warning(f"Invalid API key for user: {username}")
            return jsonify({
                "valid": False,
                "message": "Invalid API key"
            }), 200
        
        # Check if user is active
        if not user['user_data'].get('active', False):
            logger.warning(f"Inactive user attempted login: {username}")
            return jsonify({
                "valid": False,
                "message": "Account is inactive"
            }), 200
        
        # All validations passed
        logger.info(f"Successful validation for user: {username}")
        return jsonify({
            "valid": True,
            "message": "Credentials validated successfully",
            "user_data": user['user_data']
        }), 200
        
    except Exception as e:
        logger.error(f"Error during validation: {str(e)}")
        return jsonify({
            "valid": False,
            "message": "Server error during validation"
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Root endpoint."""
    return jsonify({
        "service": "QuoTrading Cloud Validation Server",
        "version": "1.0.0",
        "endpoints": {
            "/api/validate": "POST - Validate user credentials",
            "/api/health": "GET - Health check"
        }
    }), 200


if __name__ == '__main__':
    logger.info("Starting QuoTrading Cloud Validation Server...")
    logger.info("Available test users:")
    for username in USER_DATABASE.keys():
        logger.info(f"  - {username}")
    
    # Run the server
    # For production, use a proper WSGI server like gunicorn
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=True  # Set to False in production
    )
