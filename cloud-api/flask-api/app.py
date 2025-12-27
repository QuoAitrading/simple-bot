"""QuoTrading Flask API.

Simple, reliable API that works everywhere.
Now with WebSocket support for real-time zone delivery.
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import psycopg2
from psycopg2 import pool, sql as psycopg2_sql
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, timezone
import logging
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hmac
import hashlib
import requests
import traceback

app = Flask(__name__)

# Initialize SocketIO for real-time zone delivery
# async_mode='eventlet' for production, 'threading' for development
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# WebSocket connection tracking for dashboard metrics
websocket_stats = {
    'connected_clients': {},  # sid -> {connected_at, symbols}
    'total_connections': 0,
    'total_zones_sent': 0,
    'last_zone_sent': None,
    'server_start_time': datetime.now(timezone.utc).isoformat()
}

# Security: Request size limit (prevent memory exhaustion attacks)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max request size

# Security: CORS protection - restrict to known domains
# CORS_ORIGINS can be overridden via environment variable for flexibility
# In production, set CORS_ORIGINS env var to exclude localhost
_default_cors = "https://quotrading.com,https://quotrading-flask-api.azurewebsites.net,http://localhost:8080,http://localhost:5000"
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", _default_cors).split(",")
CORS(app, resources={
    r"/api/*": {"origins": "*"},  # Allow all origins for API
})

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# PostgreSQL configuration
DB_HOST = os.environ.get("DB_HOST", "quotrading-db.postgres.database.azure.com")
DB_NAME = os.environ.get("DB_NAME", "quotrading")
DB_USER = os.environ.get("DB_USER", "quotradingadmin")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_PORT = os.environ.get("DB_PORT", "5432")

# Whop configuration
WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
WHOP_WEBHOOK_SECRET = os.environ.get("WHOP_WEBHOOK_SECRET", "")
# SECURITY: Admin API key must be set via environment variable in production
# Default is only for local development - will log warning if used
_ADMIN_API_KEY_DEFAULT = "ADMIN-DEV-KEY-2026"
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", _ADMIN_API_KEY_DEFAULT)
if ADMIN_API_KEY == _ADMIN_API_KEY_DEFAULT:
    logging.warning("⚠️ SECURITY WARNING: Using default ADMIN_API_KEY. Set ADMIN_API_KEY environment variable in production!")

# Session locking configuration
# A session is considered "active" if heartbeat received within this threshold
# Heartbeats are sent every 20 seconds by the bot
# Session expires after 60 seconds of no heartbeat - 3x heartbeat interval for crash detection while tolerating network issues
SESSION_TIMEOUT_SECONDS = 60  # 60 seconds - session expires if no heartbeat for 60 seconds (3x heartbeat interval)
WHOP_API_BASE_URL = "https://api.whop.com/api/v5"

# MULTI-SYMBOL SESSION SUPPORT
# When True, allows multiple bot instances per license key (one per symbol)
# Each symbol gets its own session, preventing conflicts when trading ES, NQ, etc. simultaneously
MULTI_SYMBOL_SESSIONS_ENABLED = True

# SYMBOL GROUPS - Micro contracts share zones with their full-size equivalents
# Key = symbol user might trade, Value = base symbol for zone lookup
SYMBOL_GROUPS = {
    # S&P 500 E-mini family
    "ES": "ES",
    "MES": "ES",
    # Nasdaq E-mini family
    "NQ": "NQ",
    "MNQ": "NQ",
    # Dow Jones E-mini family (future)
    "YM": "YM",
    "MYM": "YM",
    # Crude Oil family (future)
    "CL": "CL",
    "MCL": "CL",
    # Russell 2000 family (future)
    "RTY": "RTY",
    "M2K": "RTY",
}

def get_base_symbol(symbol: str) -> str:
    """Get the base symbol for zone lookup. MES -> ES, MNQ -> NQ, etc."""
    return SYMBOL_GROUPS.get(symbol.upper(), symbol.upper())

# TradingView Webhook Configuration
# Secret key to authenticate incoming TradingView webhooks (prevents unauthorized zone submissions)
TV_WEBHOOK_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "quotrading-tv-webhook-2025")

# Email configuration (for SendGrid or SMTP)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@quotrading.com")

# Download link for the bot EXE (Azure Blob Storage)
BOT_DOWNLOAD_URL = os.environ.get("BOT_DOWNLOAD_URL", "https://quotradingfiles.blob.core.windows.net/bot-downloads/QuoTrading_Bot.exe")

# Connection pool for PostgreSQL (reuse connections)
_db_pool = None

def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive data for logging (e.g., 'ABC123XYZ' -> 'ABC1...XYZ')
    
    Args:
        value: The sensitive string to mask (can be None)
        visible_chars: Number of characters to show at start and end
    
    Returns:
        Masked string or '***' if value is None/empty/too short
    """
    if value is None or not value or len(value) <= visible_chars * 2:
        return "***"
    return f"{value[:visible_chars]}...{value[-visible_chars:]}"

def mask_email(email: str) -> str:
    """Mask email for logging (e.g., 'user@domain.com' -> 'us***@domain.com')
    
    Args:
        email: The email address to mask (can be None)
    
    Returns:
        Masked email or '***' if invalid
    """
    if email is None or not email or '@' not in email:
        return "***"
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        return f"***@{domain}"
    return f"{local[:2]}***@{domain}"

def format_datetime_utc(dt):
    """Format datetime as UTC ISO string with 'Z' suffix.
    
    Ensures naive datetimes are treated as UTC and returns proper ISO format
    that JavaScript can parse consistently across all timezones.
    
    Args:
        dt: datetime object (can be None, naive, or timezone-aware)
    
    Returns:
        ISO format string with 'Z' suffix (e.g., '2025-12-06T17:37:44Z') or None
    """
    if dt is None:
        return None
    
    # If datetime is naive (no timezone), assume it's UTC and make it aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    # Convert to ISO format and ensure it uses 'Z' suffix for UTC
    iso_str = dt.isoformat()
    
    # Replace timezone offset with 'Z' for UTC
    if iso_str.endswith('+00:00'):
        return iso_str.replace('+00:00', 'Z')
    elif not iso_str.endswith('Z'):
        # If it's not UTC, convert to UTC first
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace('+00:00', 'Z')
    
    return iso_str

def send_license_email(email, license_key, whop_user_id=None, whop_membership_id=None):
    logging.info(f"🔍 send_license_email() called for {mask_email(email)}, license {mask_sensitive(license_key)}")
    logging.info(f"🔍 SENDGRID_API_KEY present: {bool(SENDGRID_API_KEY)}")
    logging.info(f"🔍 FROM_EMAIL: {FROM_EMAIL}")
    
    try:
        subject = "🚀 Your QuoTrading AI License Key"
        
        # Build Whop ID display if available
        whop_id_html = ""
        if whop_user_id:
            whop_id_html = f"""<p style="color: #334155; font-size: 14px; line-height: 1.6; margin: 0;">
                                <strong>Whop ID:</strong> <a href="https://whop.com" style="color: #667eea; text-decoration: none;">{whop_user_id}</a>
                            </p>"""
        
        # Build order link for footer if we have membership ID
        order_link_html = ""
        if whop_membership_id:
            order_link_html = f"""
                            <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 24px 0 0 0; text-align: center;">
                                <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 0 0 12px 0;">
                                    <strong>Order Details</strong>
                                </p>
                                <p style="color: #334155; font-size: 13px; line-height: 1.6; margin: 0 0 12px 0;">
                                    Invoice: R-{whop_membership_id[-8:]}
                                </p>
                                <p style="margin: 0;">
                                    <a href="https://whop.com/hub/memberships/{whop_membership_id}" style="display: inline-block; background: #667eea; color: #ffffff; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600; margin-right: 8px;">Access Order</a>
                                    <a href="https://whop.com/hub/memberships/{whop_membership_id}/invoice" style="display: inline-block; background: #ffffff; color: #667eea; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600; border: 2px solid #667eea;">View Invoice</a>
                                </p>
                            </div>
            """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                Welcome to QuoTrading AI
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                                Your AI-powered trading journey starts now
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Whop ID Section -->
                    <tr>
                        <td style="background: #f8fafc; padding: 20px 40px; border-bottom: 1px solid #e2e8f0;">
                            {whop_id_html}
                        </td>
                    </tr>
                    
                    <!-- License Key Box -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Thank you for subscribing! Your license key is unique to your account — do not share it. Save this email for future reference.
                            </p>
                            
                            <div style="background: #f8fafc; border-left: 4px solid #667eea; padding: 24px; border-radius: 8px; margin: 24px 0;">
                                <p style="color: #64748b; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 12px 0;">
                                    Your License Key
                                </p>
                                <p style="font-size: 26px; font-weight: 900; color: #667eea; letter-spacing: 2px; font-family: 'Courier New', monospace; margin: 0; word-break: break-all; line-height: 1.4; background: #f1f5f9; padding: 16px; border-radius: 6px; border: 3px solid #667eea;">
                                    {license_key}
                                </p>
                            </div>
                            
                            <!-- Getting Started -->
                            <h2 style="color: #1e293b; font-size: 20px; font-weight: 700; margin: 32px 0 16px 0;">
                                Getting Started
                            </h2>
                            
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px 0;">
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                            <strong style="color: #667eea;">1.</strong> <strong>Download the AI</strong> — Check your email for the download link
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                            <strong style="color: #667eea;">2.</strong> <strong>Launch the application</strong> — Run the QuoTrading AI on your computer
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                            <strong style="color: #667eea;">3.</strong> <strong>Enter your license key</strong> — Paste the key above when prompted
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                            <strong style="color: #667eea;">4.</strong> <strong>Connect your broker</strong> — Enter your brokerage API credentials (username and API key)
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;">
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                            <strong style="color: #667eea;">5.</strong> <strong>Start trading</strong> — Begin using AI-powered market analysis
                                        </p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Important Notes -->
                            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px 20px; border-radius: 8px; margin: 24px 0 16px 0;">
                                <p style="color: #92400e; font-size: 14px; font-weight: 600; margin: 0 0 12px 0;">
                                    ⚠️ Important Information
                                </p>
                                <p style="color: #78350f; font-size: 14px; line-height: 1.8; margin: 0;">
                                    • You'll need API credentials from your broker to connect (contact your broker for API access)
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Order Details Section -->
                    <tr>
                        <td style="padding: 0 40px 24px 40px;">
                            {order_link_html}
                        </td>
                    </tr>
                    
                    <!-- Support Section -->
                    <tr>
                        <td style="padding: 0 40px 40px 40px;">
                            <h2 style="color: #1e293b; font-size: 20px; font-weight: 700; margin: 0 0 16px 0;">
                                Need Help?
                            </h2>
                            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0 0 12px 0;">
                                <strong>📧 Email Support:</strong>
                                <a href="mailto:support@quotrading.com" style="color: #667eea; text-decoration: none;">support@quotrading.com</a>
                            </p>
                            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0;">
                                <strong>💬 Discord Community:</strong> <a href="https://discord.gg/QzyfKDsa" style="color: #667eea; text-decoration: none;">Join our Discord</a> for live support and to connect with other traders
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f8fafc; padding: 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0 0 8px 0;">
                                Your subscription renews monthly and can be managed anytime from your Whop dashboard.
                            </p>
                            <p style="color: #94a3b8; font-size: 12px; margin: 0 0 12px 0;">
                                © 2025 QuoTrading. All rights reserved.
                            </p>
                            <p style="color: #94a3b8; font-size: 11px; margin: 0;">
                                This is a transactional email for your license purchase. To manage your subscription, visit 
                                <a href="https://whop.com/hub/memberships" style="color: #667eea; text-decoration: none;">Whop Dashboard</a>
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
        
        # Try SendGrid first (preferred), fall back to SMTP
        if SENDGRID_API_KEY:
            logging.info(f"🔍 Attempting SendGrid email to {mask_email(email)}")
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": FROM_EMAIL, "name": "QuoTrading"},
                    "reply_to": {"email": "support@quotrading.com", "name": "QuoTrading Support"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                    "tracking_settings": {
                        "click_tracking": {"enable": True},
                        "open_tracking": {"enable": True}
                    },
                    "mail_settings": {
                        "bypass_list_management": {"enable": False},
                        "footer": {"enable": False}
                    }
                }
                # Don't log payload - contains email addresses
                
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=10
                )
                logging.info(f"🔍 SendGrid response: status={response.status_code}")
                
                if response.status_code == 202:
                    logging.info(f"✅ SendGrid email sent successfully to {mask_email(email)}")
                    return True
                else:
                    logging.error(f"❌ SendGrid failed: {response.status_code}")
                    logging.warning(f"Trying SMTP fallback")
            except Exception as e:
                logging.error(f"❌ SendGrid exception: {type(e).__name__}: {str(e)}")
                logging.warning(f"Trying SMTP fallback")
        else:
            logging.warning(f"⚠️ SENDGRID_API_KEY not configured")
        
        # Fallback to SMTP (Gmail, etc.)
        if SMTP_USERNAME and SMTP_PASSWORD:
            logging.info(f"🔍 Attempting SMTP email to {mask_email(email)}")
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = FROM_EMAIL
                msg['To'] = email
                msg.attach(MIMEText(html_body, 'html'))
                
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.send_message(msg)
                logging.info(f"✅ SMTP email sent successfully to {mask_email(email)}")
                return True
            except Exception as e:
                logging.error(f"❌ SMTP exception: {type(e).__name__}: {str(e)}")
                logging.error(f"❌ No email method worked")
                return False
        else:
            logging.error(f"❌ No email method configured - SMTP credentials missing")
            return False
            
    except Exception as e:
        logging.error(f"❌ CRITICAL ERROR in send_license_email: {type(e).__name__}: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return False

def send_renewal_email(email, renewal_date, next_billing_date, whop_membership_id=None):
    """Send subscription renewal confirmation email"""
    logging.info(f"🔍 Sending renewal email to {mask_email(email)}")
    
    try:
        subject = "✅ QuoTrading AI Subscription Renewed"
        
        # Build order link if we have membership ID
        order_link_html = ""
        if whop_membership_id:
            order_link_html = f"""
                            <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 24px 0 0 0; text-align: center;">
                                <p style="margin: 0;">
                                    <a href="https://whop.com/hub/memberships/{whop_membership_id}" style="display: inline-block; background: #667eea; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">Manage Subscription</a>
                                </p>
                            </div>
            """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                ✅ Subscription Renewed
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                                Your QuoTrading AI subscription has been renewed
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Great news! Your monthly QuoTrading AI subscription was successfully renewed on <strong>{renewal_date}</strong>.
                            </p>
                            
                            <div style="background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-left: 4px solid #10b981; padding: 24px; border-radius: 8px; margin: 24px 0;">
                                <p style="color: #64748b; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 12px 0;">
                                    Renewal Details
                                </p>
                                <p style="color: #334155; font-size: 15px; line-height: 1.8; margin: 0 0 8px 0;">
                                    <strong>Renewed:</strong> {renewal_date}
                                </p>
                                <p style="color: #334155; font-size: 15px; line-height: 1.8; margin: 0;">
                                    <strong>Next Billing Date:</strong> {next_billing_date}
                                </p>
                            </div>
                            
                            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 24px 0 0 0;">
                                Your AI continues to analyze markets and provide trading signals. No action needed — keep trading!
                            </p>
                            {order_link_html}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f8fafc; padding: 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0 0 8px 0;">
                                Questions? Contact <a href="mailto:support@quotrading.com" style="color: #667eea; text-decoration: none;">support@quotrading.com</a>
                            </p>
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                                © 2025 QuoTrading. All rights reserved.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
        
        # Try SendGrid first
        if SENDGRID_API_KEY:
            logging.info(f"🔍 Attempting SendGrid renewal email to {mask_email(email)}")
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": FROM_EMAIL, "name": "QuoTrading"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}]
                }
                
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                logging.info(f"🔍 SendGrid response: status={response.status_code}")
                
                if response.status_code == 202:
                    logging.info(f"✅ SendGrid renewal email sent successfully to {mask_email(email)}")
                    return True
                else:
                    logging.error(f"SendGrid renewal email failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                logging.error(f"SendGrid renewal email error: {e}")
                return False
        else:
            logging.error(f"❌ No email method configured")
            return False
            
    except Exception as e:
        logging.error(f"❌ ERROR in send_renewal_email: {e}")
        return False

def send_cancellation_email(email, cancellation_date, access_until_date, whop_membership_id=None):
    """Send subscription cancellation confirmation email"""
    logging.info(f"🔍 Sending cancellation email to {mask_email(email)}")
    
    try:
        subject = "QuoTrading AI Subscription Cancelled"
        
        # Build reactivate link if we have membership ID
        reactivate_link_html = ""
        if whop_membership_id:
            reactivate_link_html = f"""
                            <div style="text-align: center; margin: 24px 0 0 0;">
                                <p style="color: #334155; font-size: 15px; margin: 0 0 12px 0;">
                                    Changed your mind?
                                </p>
                                <a href="https://whop.com/hub/memberships/{whop_membership_id}" style="display: inline-block; background: #667eea; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">Reactivate Subscription</a>
                            </div>
            """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #64748b 0%, #475569 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                Subscription Cancelled
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                                We're sorry to see you go
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Your QuoTrading AI subscription has been cancelled as of <strong>{cancellation_date}</strong>.
                            </p>
                            
                            <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-left: 4px solid #f59e0b; padding: 24px; border-radius: 8px; margin: 24px 0;">
                                <p style="color: #92400e; font-size: 14px; font-weight: 600; margin: 0 0 12px 0;">
                                    ⚠️ Important Information
                                </p>
                                <p style="color: #78350f; font-size: 14px; line-height: 1.8; margin: 0 0 8px 0;">
                                    • You'll retain access until <strong>{access_until_date}</strong>
                                </p>
                                <p style="color: #78350f; font-size: 14px; line-height: 1.8; margin: 0;">
                                    • No further charges will be made
                                </p>
                            </div>
                            
                            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 24px 0 0 0;">
                                Thank you for using QuoTrading AI. We'd love to have you back anytime!
                            </p>
                            {reactivate_link_html}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f8fafc; padding: 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0 0 8px 0;">
                                Questions? Contact <a href="mailto:support@quotrading.com" style="color: #667eea; text-decoration: none;">support@quotrading.com</a>
                            </p>
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                                © 2025 QuoTrading. All rights reserved.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
        
        # Try SendGrid
        if SENDGRID_API_KEY:
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": FROM_EMAIL, "name": "QuoTrading"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}]
                }
                
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 202:
                    logging.info(f"✅ Cancellation email sent to {mask_email(email)}")
                    return True
                else:
                    logging.error(f"Cancellation email failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                logging.error(f"Cancellation email error: {e}")
                return False
        else:
            logging.error(f"❌ No email method configured")
            return False
            
    except Exception as e:
        logging.error(f"❌ ERROR in send_cancellation_email: {e}")
        return False

def send_payment_failed_email(email, retry_date, whop_membership_id=None):
    """Send payment failure notification email"""
    logging.info(f"🔍 Sending payment failed email to {mask_email(email)}")
    
    try:
        subject = "⚠️ QuoTrading AI Payment Failed"
        
        # Build update payment link if we have membership ID
        update_payment_html = ""
        if whop_membership_id:
            update_payment_html = f"""
                            <div style="text-align: center; margin: 24px 0 0 0;">
                                <a href="https://whop.com/hub/memberships/{whop_membership_id}" style="display: inline-block; background: #ef4444; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">Update Payment Method</a>
                            </div>
            """
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                ⚠️ Payment Failed
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                                Action required to continue your subscription
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                We were unable to process your recent payment for QuoTrading AI. This could be due to insufficient funds, an expired card, or a temporary issue with your payment method.
                            </p>
                            
                            <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); border-left: 4px solid #ef4444; padding: 24px; border-radius: 8px; margin: 24px 0;">
                                <p style="color: #991b1b; font-size: 14px; font-weight: 600; margin: 0 0 12px 0;">
                                    ⚠️ Immediate Action Required
                                </p>
                                <p style="color: #7f1d1d; font-size: 14px; line-height: 1.8; margin: 0 0 8px 0;">
                                    • Your subscription is temporarily suspended
                                </p>
                                <p style="color: #7f1d1d; font-size: 14px; line-height: 1.8; margin: 0;">
                                    • Payment will be retried on <strong>{retry_date}</strong>
                                </p>
                            </div>
                            
                            <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 24px 0 0 0;">
                                <strong>To restore access:</strong> Please update your payment method below to avoid service interruption.
                            </p>
                            {update_payment_html}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f8fafc; padding: 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0 0 8px 0;">
                                Questions? Contact <a href="mailto:support@quotrading.com" style="color: #667eea; text-decoration: none;">support@quotrading.com</a>
                            </p>
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                                © 2025 QuoTrading. All rights reserved.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
        
        # Try SendGrid
        if SENDGRID_API_KEY:
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": FROM_EMAIL, "name": "QuoTrading"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}]
                }
                
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 202:
                    logging.info(f"✅ Payment failed email sent to {mask_email(email)}")
                    return True
                else:
                    logging.error(f"Payment failed email failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                logging.error(f"Payment failed email error: {e}")
                return False
        else:
            logging.error(f"❌ No email method configured")
            return False
            
    except Exception as e:
        logging.error(f"❌ ERROR in send_payment_failed_email: {e}")
        return False

def send_subscription_expired_email(email, expiration_date):
    """Send subscription expiration notification email"""
    logging.info(f"🔍 Sending subscription expired email to {mask_email(email)}")
    
    try:
        subject = "QuoTrading AI Subscription Expired"
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07); overflow: hidden;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #64748b 0%, #475569 100%); padding: 40px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">
                                Subscription Expired
                            </h1>
                            <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                                Your QuoTrading AI access has ended
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            <p style="color: #334155; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                Your QuoTrading AI subscription expired on <strong>{expiration_date}</strong>. Your license key is no longer active.
                            </p>
                            
                            <div style="background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%); border-left: 4px solid #667eea; padding: 24px; border-radius: 8px; margin: 24px 0;">
                                <p style="color: #475569; font-size: 14px; font-weight: 600; margin: 0 0 12px 0;">
                                    💡 Want to Continue Trading?
                                </p>
                                <p style="color: #64748b; font-size: 14px; line-height: 1.8; margin: 0;">
                                    Reactivate your subscription to regain access to AI-powered market analysis and trading signals.
                                </p>
                            </div>
                            
                            <div style="text-align: center; margin: 24px 0 0 0;">
                                <a href="https://whop.com" style="display: inline-block; background: #667eea; color: #ffffff; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600;">Reactivate Subscription</a>
                            </div>
                            
                            <p style="color: #64748b; font-size: 14px; line-height: 1.6; margin: 24px 0 0 0; text-align: center;">
                                Thank you for being part of the QuoTrading community!
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f8fafc; padding: 32px; text-align: center; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; font-size: 13px; line-height: 1.6; margin: 0 0 8px 0;">
                                Questions? Contact <a href="mailto:support@quotrading.com" style="color: #667eea; text-decoration: none;">support@quotrading.com</a>
                            </p>
                            <p style="color: #94a3b8; font-size: 12px; margin: 0;">
                                © 2025 QuoTrading. All rights reserved.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
        
        # Try SendGrid
        if SENDGRID_API_KEY:
            try:
                payload = {
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": FROM_EMAIL, "name": "QuoTrading"},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}]
                }
                
                response = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 202:
                    logging.info(f"✅ Subscription expired email sent to {mask_email(email)}")
                    return True
                else:
                    logging.error(f"Expired email failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                logging.error(f"Expired email error: {e}")
                return False
        else:
            logging.error(f"❌ No email method configured")
            return False
            
    except Exception as e:
        logging.error(f"❌ ERROR in send_subscription_expired_email: {e}")
        return False

def generate_license_key():
    """Generate a unique license key"""
    characters = string.ascii_uppercase + string.digits
    segments = []
    for _ in range(4):
        segment = ''.join(secrets.choice(characters) for _ in range(4))
        segments.append(segment)
    return '-'.join(segments)  # Format: XXXX-XXXX-XXXX-XXXX

# Rate limiting: track submissions per license key
_rate_limit_cache = {}  # {license_key: [timestamp1, timestamp2, ...]}
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 100  # max submissions per window

def check_rate_limit(license_key, endpoint="unknown"):
    """Check if license key is within rate limits. Returns (allowed: bool, message: str)"""
    import time
    current_time = time.time()
    
    # Clean old entries
    if license_key in _rate_limit_cache:
        _rate_limit_cache[license_key] = [
            ts for ts in _rate_limit_cache[license_key] 
            if current_time - ts < _RATE_LIMIT_WINDOW
        ]
    else:
        _rate_limit_cache[license_key] = []
    
    # Check limit
    submission_count = len(_rate_limit_cache[license_key])
    if submission_count >= _RATE_LIMIT_MAX:
        # Log security event
        log_security_event(license_key, endpoint, submission_count, f"Rate limit exceeded: {submission_count}/{_RATE_LIMIT_MAX} in {_RATE_LIMIT_WINDOW}s")
        return False, f"Rate limit exceeded: {submission_count} submissions in last {_RATE_LIMIT_WINDOW}s (max {_RATE_LIMIT_MAX})"
    
    # Add current submission
    _rate_limit_cache[license_key].append(current_time)
    return True, "OK"

def log_security_event(license_key, endpoint, attempts, reason):
    """Log security event (rate limit, suspicious activity) to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        # Get user email for better tracking
        email = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT email FROM users WHERE license_key = %s", (license_key,))
            user = cur.fetchone()
            if user:
                email = user[0]
            cur.close()
        except:
            pass
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO security_events (license_key, email, endpoint, attempts, reason, timestamp)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (license_key, email, endpoint, attempts, reason))
        conn.commit()
        cur.close()
        return_connection(conn)
    except Exception as e:
        logging.error(f"Failed to log security event: {e}")

def log_webhook_event(event_type, status, whop_id=None, user_id=None, email=None, details=None, error=None, payload=None):
    """Log webhook event to database for debugging"""
    try:
        conn = get_db_connection()
        if not conn:
            return
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO webhook_events (event_type, whop_id, user_id, email, status, details, error, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (event_type, whop_id, user_id, email, status, details, error, json.dumps(payload) if payload else None))
        conn.commit()
        cur.close()
        return_connection(conn)
    except Exception as e:
        logging.error(f"Failed to log webhook event: {e}")

def init_db_pool():
    """Initialize PostgreSQL connection pool for reusing connections"""
    global _db_pool
    
    if _db_pool is not None:
        return _db_pool
    
    try:
        # Try standard username first
        try:
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=2,
                maxconn=20,
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                sslmode='require',
                connect_timeout=10
            )
            logging.info("✅ PostgreSQL connection pool initialized (2-20 connections)")
            return _db_pool
        except psycopg2.OperationalError:
            # Fallback for flexible server format
            user_with_server = f"{DB_USER}@{DB_HOST.split('.')[0]}" if '@' not in DB_USER else DB_USER
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=2,
                maxconn=20,
                host=DB_HOST,
                database=DB_NAME,
                user=user_with_server,
                password=DB_PASSWORD,
                sslmode='require',
                connect_timeout=10
            )
            logging.info("✅ PostgreSQL connection pool initialized (2-20 connections)")
            return _db_pool
    except Exception as e:
        logging.error(f"❌ Failed to initialize connection pool: {e}")
        return None

def get_db_connection():
    """Get PostgreSQL database connection from pool with timeout protection"""
    global _db_pool
    
    # Initialize pool if not exists
    if _db_pool is None:
        init_db_pool()
    
    try:
        if _db_pool:
            conn = _db_pool.getconn()
            if conn:
                # Set statement timeout to prevent slow queries from hanging
                try:
                    cur = conn.cursor()
                    cur.execute("SET statement_timeout = '30s'")  # 30 second query timeout
                    conn.commit()
                    cur.close()
                except:
                    pass
                return conn
        
        # Fallback to direct connection if pool fails
        logging.warning("Pool unavailable, creating direct connection")
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                sslmode='require',
                connect_timeout=10
            )
            return conn
        except psycopg2.OperationalError:
            user_with_server = f"{DB_USER}@{DB_HOST.split('.')[0]}" if '@' not in DB_USER else DB_USER
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=user_with_server,
                password=DB_PASSWORD,
                sslmode='require',
                connect_timeout=10
            )
            return conn
            
    except Exception as e:
        logging.error(f"❌ Database connection failed: {e}")
        logging.error(f"   Host: {DB_HOST}, User: {DB_USER}, DB: {DB_NAME}")
        return None

def return_connection(conn):
    """Return connection to pool or close if from direct connection"""
    global _db_pool
    
    if conn is None:
        return
    
    try:
        if _db_pool:
            _db_pool.putconn(conn)
        else:
            # Close direct connection if pool not available
            conn.close()
    except Exception as e:
        logging.error(f"Error returning connection: {e}")
        try:
            conn.close()
        except:
            pass

def validate_license(license_key: str):
    """Validate license key against PostgreSQL database
    
    Returns:
        Tuple of (is_valid: bool, message: str, expiration_date: datetime or None)
    """
    if not license_key:
        return False, "License key required", None
    
    # Check if it's the admin development key (server-side only, never exposed to client)
    if license_key == ADMIN_API_KEY:
        logging.info(f"✅ Admin key validated")
        # Return valid with no expiration for admin key
        return True, "Valid Admin License", None
    
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed", None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT license_key, email, license_type, license_status, 
                       license_expiration, created_at
                FROM users 
                WHERE license_key = %s
            """, (license_key,))
            
            user = cursor.fetchone()
            
            if not user:
                return False, "Invalid license key", None
            
            # Check if license is active (case-insensitive)
            if user['license_status'].lower() != 'active':
                return False, f"License is {user['license_status']}", user['license_expiration']
            
            # Check expiration
            if user['license_expiration']:
                # Ensure timezone-aware comparison
                now_utc = datetime.now(timezone.utc)
                expiration = user['license_expiration']
                # If expiration is naive, make it UTC-aware
                if expiration.tzinfo is None:
                    expiration = expiration.replace(tzinfo=timezone.utc)
                if now_utc > expiration:
                    return False, "License expired", user['license_expiration']
            
            # Log successful validation
            cursor.execute("""
                INSERT INTO api_logs (license_key, endpoint, request_data, status_code)
                VALUES (%s, %s, %s, %s)
            """, (license_key, '/api/main', '{"action": "validate"}', 200))
            conn.commit()
            
            return True, f"Valid {user['license_type']} license", user['license_expiration']
            
    except Exception as e:
        logging.error(f"License validation error: {e}")
        return False, str(e), None
    finally:
        return_connection(conn)

def ensure_active_sessions_table(conn):
    """
    Create the active_sessions table if it doesn't exist.
    This table enables multi-symbol session support.
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_sessions (
                    id SERIAL PRIMARY KEY,
                    license_key VARCHAR(255) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    device_fingerprint VARCHAR(255) NOT NULL,
                    last_heartbeat TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW(),
                    metadata JSONB,
                    UNIQUE(license_key, symbol)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_sessions_license 
                ON active_sessions(license_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_sessions_license_symbol 
                ON active_sessions(license_key, symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_sessions_heartbeat 
                ON active_sessions(last_heartbeat)
            """)
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Failed to create active_sessions table: {e}")
        return False


def check_symbol_session_conflict(conn, license_key: str, symbol: str, device_fingerprint: str, allow_same_device: bool = False):
    """
    Check if there's an active session for this license+symbol combination.
    
    Args:
        allow_same_device: If True, same device can continue (used for heartbeats)
                          If False, ALL devices blocked (used for validation/login)
    
    Returns:
        Tuple of (has_conflict: bool, session_info: dict or None)
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT device_fingerprint, last_heartbeat, metadata
                FROM active_sessions
                WHERE license_key = %s AND symbol = %s
            """, (license_key, symbol))
            session = cursor.fetchone()
            
            if not session:
                return False, None
            
            stored_device = session[0]
            last_heartbeat = session[1]
            metadata = session[2]
            
            # Check if session is still active (within timeout)
            if last_heartbeat:
                now_utc = datetime.now(timezone.utc)
                heartbeat = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=timezone.utc)
                time_since_last = now_utc - heartbeat
                
                logging.info(f"🔍 Session check for {license_key}/{symbol}: time_since_last={int(time_since_last.total_seconds())}s, timeout={SESSION_TIMEOUT_SECONDS}s, allow_same_device={allow_same_device}, stored_device={stored_device[:8]}..., requested_device={device_fingerprint[:8]}...")
                
                if time_since_last < timedelta(seconds=SESSION_TIMEOUT_SECONDS):
                    # Active session exists
                    if allow_same_device and stored_device == device_fingerprint:
                        # Heartbeat from same device - allow to continue
                        logging.info(f"✅ Allowing same device to continue: {device_fingerprint[:8]}...")
                        return False, None
                    else:
                        # Different device OR validation/login - block ALL
                        same_device_str = "SAME DEVICE" if stored_device == device_fingerprint else "DIFFERENT DEVICE"
                        logging.warning(f"🚫 BLOCKING login/validation ({same_device_str}): allow_same_device={allow_same_device}, active session {int(time_since_last.total_seconds())}s old")
                        return True, {
                            "device_fingerprint": stored_device,
                            "last_heartbeat": last_heartbeat,
                            "seconds_remaining": max(0, SESSION_TIMEOUT_SECONDS - int(time_since_last.total_seconds()))
                        }
                else:
                    # Session expired - clean it up
                    logging.info(f"⏰ Session expired ({int(time_since_last.total_seconds())}s > {SESSION_TIMEOUT_SECONDS}s), cleaning up...")
                    cursor.execute("""
                        DELETE FROM active_sessions
                        WHERE license_key = %s AND symbol = %s
                    """, (license_key, symbol))
                    conn.commit()
                    logging.info(f"🧹 Cleaned up expired session for {license_key}/{symbol}")
                    return False, None
            else:
                # No heartbeat - session is stale
                return False, None
                
    except Exception as e:
        logging.error(f"Error checking symbol session: {e}")
        return False, None


def create_or_update_symbol_session(conn, license_key: str, symbol: str, device_fingerprint: str, metadata: dict = None):
    """
    Create or update a session for a specific license+symbol combination.
    """
    try:
        with conn.cursor() as cursor:
            # Use UPSERT to create or update the session
            cursor.execute("""
                INSERT INTO active_sessions (license_key, symbol, device_fingerprint, last_heartbeat, metadata)
                VALUES (%s, %s, %s, NOW(), %s)
                ON CONFLICT (license_key, symbol) 
                DO UPDATE SET 
                    device_fingerprint = EXCLUDED.device_fingerprint,
                    last_heartbeat = NOW(),
                    metadata = EXCLUDED.metadata
            """, (license_key, symbol, device_fingerprint, json.dumps(metadata) if metadata else None))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error creating/updating symbol session: {e}")
        return False


def release_symbol_session(conn, license_key: str, symbol: str, device_fingerprint: str):
    """
    Release a session for a specific license+symbol combination by deleting it from the database.
    This allows immediate re-login after normal shutdown.
    
    Only deletes if the device_fingerprint matches (prevents unauthorized releases).
    
    Returns:
        True if session was deleted, False otherwise
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE FROM active_sessions
                WHERE license_key = %s AND symbol = %s AND device_fingerprint = %s
            """, (license_key, symbol, device_fingerprint))
            deleted = cursor.rowcount
            conn.commit()
            return deleted > 0
    except Exception as e:
        logging.error(f"Error releasing symbol session: {e}")
        return False


def count_active_symbol_sessions(conn, license_key: str):
    """
    Count the number of active symbol sessions for a license.
    Returns count of non-expired sessions.
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM active_sessions
                WHERE license_key = %s 
                AND last_heartbeat > NOW() - make_interval(secs => %s)
            """, (license_key, SESSION_TIMEOUT_SECONDS))
            result = cursor.fetchone()
            return result[0] if result else 0
    except Exception as e:
        logging.error(f"Error counting symbol sessions: {e}")
        return 0


def load_experiences(symbol='ES'):
    """Deprecated no-op; kept temporarily for older clients."""
    return []


# =============================================================================
# ZONES TABLE & FUNCTIONS - TradingView Integration
# =============================================================================

def ensure_zones_table(conn):
    """
    Create the zones table if it doesn't exist.
    Stores supply/demand zones from TradingView alerts.
    """
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    id SERIAL PRIMARY KEY,
                    base_symbol VARCHAR(10) NOT NULL,
                    zone_type VARCHAR(10) NOT NULL,
                    top_price DECIMAL(12, 4) NOT NULL,
                    bottom_price DECIMAL(12, 4) NOT NULL,
                    strength VARCHAR(10) DEFAULT 'MEDIUM',
                    status VARCHAR(10) DEFAULT 'FRESH',
                    retests INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours'),
                    source VARCHAR(20) DEFAULT 'tradingview',
                    metadata JSONB DEFAULT '{}'::jsonb
                )
            """)
            # Index for fast lookups by symbol and active zones
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_zones_symbol_active 
                ON zones (base_symbol, expires_at) 
                WHERE status != 'MITIGATED'
            """)
            conn.commit()
            logging.info("✅ Zones table ensured")
    except Exception as e:
        logging.error(f"Error creating zones table: {e}")
        conn.rollback()


def store_zone(conn, base_symbol: str, zone_type: str, top_price: float, bottom_price: float, 
               strength: str = "MEDIUM", expires_hours: int = 24, metadata: dict = None):
    """
    Store a new zone in the database.
    
    Args:
        base_symbol: Base symbol (ES, NQ, etc.)
        zone_type: 'supply' or 'demand'
        top_price: Top of zone
        bottom_price: Bottom of zone
        strength: Zone strength (STRONG, MEDIUM, WEAK)
        expires_hours: Hours until zone expires (default 24)
        metadata: Additional metadata dict
    
    Returns:
        Zone ID if successful, None otherwise
    """
    try:
        ensure_zones_table(conn)
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO zones (base_symbol, zone_type, top_price, bottom_price, strength, expires_at, metadata)
                VALUES (%s, %s, %s, %s, %s, NOW() + make_interval(hours => %s), %s)
                RETURNING id
            """, (
                base_symbol.upper(),
                zone_type.lower(),
                top_price,
                bottom_price,
                strength.upper(),
                expires_hours,
                json.dumps(metadata or {})
            ))
            zone_id = cursor.fetchone()[0]
            conn.commit()
            logging.info(f"✅ Stored zone {zone_id}: {zone_type.upper()} {base_symbol} [{bottom_price}-{top_price}]")
            return zone_id
    except Exception as e:
        logging.error(f"Error storing zone: {e}")
        conn.rollback()
        return None


def get_zones_for_symbol(symbol: str) -> list:
    """
    Get active zones for a symbol (including micro contract equivalents).
    
    Args:
        symbol: Trading symbol (ES, MES, NQ, MNQ, etc.)
    
    Returns:
        List of zone dicts with zone_type, top, bottom, strength, status
    """
    base_symbol = get_base_symbol(symbol)
    zones = []
    
    conn = get_db_connection()
    if not conn:
        return zones
    
    try:
        ensure_zones_table(conn)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    zone_type,
                    top_price as top,
                    bottom_price as bottom,
                    strength,
                    status,
                    retests,
                    created_at,
                    expires_at
                FROM zones
                WHERE base_symbol = %s
                AND status != 'MITIGATED'
                AND expires_at > NOW()
                ORDER BY created_at DESC
                LIMIT 20
            """, (base_symbol,))
            
            rows = cursor.fetchall()
            for row in rows:
                zones.append({
                    "id": row["id"],
                    "type": row["zone_type"],
                    "top": float(row["top"]),
                    "bottom": float(row["bottom"]),
                    "strength": row["strength"],
                    "status": row["status"],
                    "retests": row["retests"],
                    "created_at": format_datetime_utc(row["created_at"]),
                    "expires_at": format_datetime_utc(row["expires_at"])
                })
    except Exception as e:
        logging.error(f"Error getting zones for {symbol}: {e}")
    finally:
        return_connection(conn)
    
    return zones


def mark_zone_mitigated(zone_id: int):
    """Mark a zone as mitigated (price broke through it)."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE zones SET status = 'MITIGATED' WHERE id = %s
            """, (zone_id,))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error marking zone mitigated: {e}")
        return False
    finally:
        return_connection(conn)


def increment_zone_retest(zone_id: int):
    """Increment retest count for a zone."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE zones 
                SET retests = retests + 1, 
                    status = CASE WHEN retests = 0 THEN 'TESTED' ELSE status END
                WHERE id = %s
            """, (zone_id,))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error incrementing zone retest: {e}")
        return False
    finally:
        return_connection(conn)

@app.route('/api/hello', methods=['GET'])
def hello():
    """Health check endpoint"""
    return jsonify({
        "status": "success",
        "message": "✅ QuoTrading Cloud API - Data Collection Only",
        "endpoints": [
            "POST /api/heartbeat - Bot heartbeat (equity/PnL)",
            "POST /api/tv-webhook - TradingView zone alerts",
            "GET /api/zones/<symbol> - Get active zones for symbol",
            "GET /api/profile - Get user profile and trading statistics",
            "GET /api/hello - Health check"
        ],
        "database_configured": bool(DB_PASSWORD),
        "note": "Bots make decisions locally"
    }), 200


@app.route('/api/tv-webhook', methods=['POST'])
def tradingview_webhook():
    """
    Receive zone alerts from TradingView PineScript indicator.
    
    TradingView sends JSON payload when alert triggers:
    {
        "secret": "quotrading-tv-webhook-2025",
        "symbol": "ES",
        "zone_type": "supply" or "demand",
        "top": 6050.25,
        "bottom": 6048.50,
        "strength": "STRONG" or "MEDIUM" or "WEAK",
        "timeframe": "5m" (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        # Authenticate webhook (prevent unauthorized submissions)
        secret = data.get("secret", "")
        if secret != TV_WEBHOOK_SECRET:
            logging.warning(f"⚠️ Invalid TV webhook secret attempt")
            return jsonify({"status": "error", "message": "Invalid secret"}), 403
        
        # Extract zone data
        symbol = data.get("symbol", "").upper()
        zone_type = data.get("zone_type", "").lower()
        top_price = data.get("top")
        bottom_price = data.get("bottom")
        strength = data.get("strength", "MEDIUM").upper()
        timeframe = data.get("timeframe", "")
        
        # Validation
        if not symbol:
            return jsonify({"status": "error", "message": "Symbol required"}), 400
        if zone_type not in ["supply", "demand"]:
            return jsonify({"status": "error", "message": "zone_type must be 'supply' or 'demand'"}), 400
        if top_price is None or bottom_price is None:
            return jsonify({"status": "error", "message": "top and bottom prices required"}), 400
        if strength not in ["STRONG", "MEDIUM", "WEAK"]:
            strength = "MEDIUM"
        
        # Get base symbol for storage (MES -> ES, MNQ -> NQ)
        base_symbol = get_base_symbol(symbol)
        
        # Store the zone
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database unavailable"}), 500
        
        try:
            metadata = {
                "source_symbol": symbol,
                "timeframe": timeframe,
                "received_at": datetime.now(timezone.utc).isoformat()
            }
            
            zone_id = store_zone(
                conn=conn,
                base_symbol=base_symbol,
                zone_type=zone_type,
                top_price=float(top_price),
                bottom_price=float(bottom_price),
                strength=strength,
                expires_hours=24,
                metadata=metadata
            )
            
            if zone_id:
                logging.info(f"📊 TradingView Zone Received: {zone_type.upper()} {base_symbol} [{bottom_price}-{top_price}] strength={strength}")
                
                # REAL-TIME: Broadcast zone to all connected clients for this symbol
                zone_data = {
                    "id": zone_id,
                    "type": zone_type,
                    "top": float(top_price),
                    "bottom": float(bottom_price),
                    "strength": strength,
                    "status": "FRESH",
                    "retests": 0,
                    "created_at": datetime.now(timezone.utc).isoformat() + "Z"
                }
                # Broadcast to base symbol room (ES users AND MES users get this)
                socketio.emit('new_zone', zone_data, room=base_symbol)
                logging.info(f"📡 Broadcasted zone to room: {base_symbol}")
                
                return jsonify({
                    "status": "success",
                    "message": f"Zone stored and broadcasted",
                    "zone_id": zone_id,
                    "base_symbol": base_symbol,
                    "zone_type": zone_type,
                    "broadcasted_to": base_symbol
                }), 200
            else:
                return jsonify({"status": "error", "message": "Failed to store zone"}), 500
                
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"TradingView webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/zones/<symbol>', methods=['GET'])
def get_zones_endpoint(symbol):
    """
    Get active zones for a symbol.
    MES gets ES zones, MNQ gets NQ zones (shared base symbol).
    """
    try:
        zones = get_zones_for_symbol(symbol)
        base_symbol = get_base_symbol(symbol)
        return jsonify({
            "status": "success",
            "symbol": symbol.upper(),
            "base_symbol": base_symbol,
            "zones": zones,
            "count": len(zones)
        }), 200
    except Exception as e:
        logging.error(f"Error getting zones: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/validate-license', methods=['POST'])
def validate_license_endpoint():
    """
    Validate license key and check for session conflicts.
    This is called by the launcher BEFORE starting the bot.
    
    Parameters:
    - license_key: The license key to validate
    - device_fingerprint: Device fingerprint (may differ between launcher and bot due to PID)
    - symbol: Trading symbol for multi-symbol session support (e.g., 'ES', 'NQ')
    - check_only: If True, only validate and check conflicts WITHOUT creating session (default: False)
    
    Multi-Symbol Session Support:
    When a symbol is provided, sessions are managed per license+symbol combination,
    allowing multiple bot instances (one per symbol) to run simultaneously.
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        device_fingerprint = data.get('device_fingerprint')
        symbol = data.get('symbol')  # MULTI-SYMBOL: Optional symbol for per-symbol sessions
        check_only = data.get('check_only', False)
        
        if not license_key:
            return jsonify({
                "license_valid": False,
                "message": "License key required"
            }), 400
        
        if not device_fingerprint:
            return jsonify({
                "license_valid": False,
                "message": "Device fingerprint required"
            }), 400
        
        # Rate limiting
        allowed, rate_msg = check_rate_limit(license_key, '/api/validate-license')
        if not allowed:
            return jsonify({
                "license_valid": False,
                "message": rate_msg
            }), 429
        
        # Validate license
        is_valid, message, license_expiration = validate_license(license_key)
        if not is_valid:
            return jsonify({
                "license_valid": False,
                "message": message
            }), 401
        
        # Check for session conflicts (another device using this license)
        conn = get_db_connection()
        if conn:
            try:
                # Get license type first
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT license_type FROM users WHERE license_key = %s
                    """, (license_key,))
                    user = cursor.fetchone()
                    license_type = user[0] if user else 'STANDARD'
                
                # MULTI-SYMBOL SESSION SUPPORT
                # When symbol is provided, use per-symbol session management
                if symbol and MULTI_SYMBOL_SESSIONS_ENABLED:
                    # Ensure active_sessions table exists
                    ensure_active_sessions_table(conn)
                    
                    # Check for session conflict for this specific symbol
                    # For validation/login, use strict blocking (even same device)
                    has_conflict, conflict_info = check_symbol_session_conflict(
                        conn, license_key, symbol, device_fingerprint, allow_same_device=False
                    )
                    
                    if has_conflict:
                        logging.warning(f"⚠️ BLOCKED - License {license_key} symbol {symbol} already in use by {conflict_info['device_fingerprint'][:8]}...")
                        return jsonify({
                            "license_valid": False,
                            "session_conflict": True,
                            "message": f"Symbol {symbol} Already Active - Another session is using this symbol. If the previous instance crashed, wait {conflict_info['seconds_remaining']} seconds.",
                            "active_device": conflict_info['device_fingerprint'][:20] + "...",
                            "symbol": symbol,
                            "estimated_wait_seconds": conflict_info['seconds_remaining']
                        }), 403
                    
                    # No conflict for this symbol - validation successful
                    # NOTE: Sessions are NOT created during validation - only via heartbeat endpoint
                    # (See legacy session path below for detailed explanation)
                    active_count = count_active_symbol_sessions(conn, license_key)
                    logging.info(f"✅ License validated for {license_key}/{symbol} ({active_count} active symbols)")
                    
                    return jsonify({
                        "license_valid": True,
                        "message": f"License validated successfully for {symbol}",
                        "session_conflict": False,
                        "license_type": license_type,
                        "symbol": symbol,
                        "active_symbols": active_count,
                        "expiry_date": license_expiration.isoformat() if license_expiration else None
                    }), 200
                
                # LEGACY: No symbol provided - use original single-session logic
                # This maintains backward compatibility with older bot versions
                with conn.cursor() as cursor:
                    # STRICT ENFORCEMENT: Check if ANY symbol sessions exist for this license
                    # This prevents launcher from starting if any bot instances are running
                    if MULTI_SYMBOL_SESSIONS_ENABLED:
                        cursor.execute("""
                            SELECT symbol, device_fingerprint, last_heartbeat
                            FROM active_sessions
                            WHERE license_key = %s
                            AND last_heartbeat > NOW() - make_interval(secs => %s)
                            ORDER BY last_heartbeat DESC
                            LIMIT 1
                        """, (license_key, SESSION_TIMEOUT_SECONDS))
                        active_symbol_session = cursor.fetchone()
                        
                        if active_symbol_session:
                            # Active symbol session exists - block launcher
                            symbol = active_symbol_session[0]
                            stored_device = active_symbol_session[1]
                            last_heartbeat = active_symbol_session[2]
                            
                            now_utc = datetime.now(timezone.utc)
                            heartbeat = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=timezone.utc)
                            time_since_last = now_utc - heartbeat
                            seconds_remaining = max(0, SESSION_TIMEOUT_SECONDS - int(time_since_last.total_seconds()))
                            
                            logging.warning(f"⚠️ BLOCKED - License {license_key} has active session for symbol {symbol} on device {stored_device[:8]}...")
                            return jsonify({
                                "license_valid": False,
                                "session_conflict": True,
                                "message": f"Active Session Detected - Symbol {symbol} is currently running. If you force-closed the bot, wait {seconds_remaining} seconds.",
                                "active_device": stored_device[:20] + "...",
                                "active_symbol": symbol,
                                "estimated_wait_seconds": seconds_remaining
                            }), 403
                    
                    # Check legacy session in users table
                    cursor.execute("""
                        SELECT device_fingerprint, last_heartbeat, license_type
                        FROM users
                        WHERE license_key = %s
                    """, (license_key,))
                    user = cursor.fetchone()
                    
                    if user:
                        stored_device = user[0]
                        last_heartbeat = user[1]
                        license_type = user[2] if len(user) > 2 else 'STANDARD'
                        
                        # If there's a stored session, check if it's active
                        if stored_device:
                            # STRICT ENFORCEMENT: Check heartbeat EXISTS first, then check age
                            # This prevents bypassing restrictions - we don't blindly clear sessions
                            # Prevents API key sharing on same OR different devices
                            if last_heartbeat:
                                # Heartbeat EXISTS - calculate age
                                now_utc = datetime.now(timezone.utc)
                                heartbeat = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=timezone.utc)
                                time_since_last = now_utc - heartbeat
                                
                                # If heartbeat exists and is recent (< SESSION_TIMEOUT_SECONDS)
                                # Block ALL logins regardless of device - NO EXCEPTIONS
                                if time_since_last < timedelta(seconds=SESSION_TIMEOUT_SECONDS):
                                    # Session is still within timeout window - BLOCK
                                    # This ensures ONLY ONE active instance per API key
                                    if stored_device == device_fingerprint:
                                        logging.warning(f"⚠️ BLOCKED - Same device {device_fingerprint[:8]}... but session EXISTS (last heartbeat {int(time_since_last.total_seconds())}s ago). Only 1 instance allowed per API key.")
                                        return jsonify({
                                            "license_valid": False,
                                            "session_conflict": True,
                                            "message": "Instance Already Running - Another session is currently active on this device. If the previous instance crashed or was force-closed, please wait approximately 60 seconds before trying again.",
                                            "active_device": stored_device[:20] + "...",
                                            "estimated_wait_seconds": max(0, SESSION_TIMEOUT_SECONDS - int(time_since_last.total_seconds()))
                                        }), 403
                                    else:
                                        # Different device - BLOCK
                                        logging.warning(f"⚠️ BLOCKED - License {license_key} already in use by {stored_device[:20]}... (tried: {device_fingerprint[:20]}..., last seen {int(time_since_last.total_seconds())}s ago)")
                                        return jsonify({
                                            "license_valid": False,
                                            "session_conflict": True,
                                            "message": "License In Use - This license is currently active on another device. Only one active session is allowed per license.",
                                            "active_device": stored_device[:20] + "...",
                                            "estimated_wait_seconds": max(0, SESSION_TIMEOUT_SECONDS - int(time_since_last.total_seconds()))
                                        }), 403
                                
                                # Session fully expired (>= 60s) - allow takeover
                                # Only after checking heartbeat EXISTS and is OLD do we allow login
                                else:
                                    logging.info(f"🧹 Expired session (last seen {int(time_since_last.total_seconds())}s ago) - allowing takeover by {device_fingerprint[:8]}...")
                            else:
                                # No heartbeat timestamp - session was cleanly released, allow login
                                logging.info(f"✅ No heartbeat found - allowing {device_fingerprint[:8]}...")
                    
                    # No conflict detected - validation successful
                    # NOTE: Sessions are NOT created during validation - only via heartbeat endpoint
                    # This prevents race conditions where bot crashes immediately after validation
                    # creating a session lock that blocks immediate reconnection attempts
                    logging.info(f"✅ License validated for {license_key} - {license_type} expires {license_expiration}")
                    
                    return jsonify({
                        "license_valid": True,
                        "message": "License validated successfully",
                        "session_conflict": False,
                        "license_type": license_type,
                        "expiry_date": license_expiration.isoformat() if license_expiration else None
                    }), 200
            finally:
                return_connection(conn)
        
        return jsonify({
            "license_valid": False,
            "message": "Database error"
        }), 500
        
    except Exception as e:
        logging.error(f"License validation error: {e}")
        return jsonify({
            "license_valid": False,
            "message": str(e)
        }), 500

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """
    Record bot heartbeat for online status tracking with session locking.
    
    Parameters:
    - license_key: The license key
    - device_fingerprint: Device fingerprint
    - symbol: Trading symbol for multi-symbol session support (optional)
    - metadata: Additional metadata (status, bot_version, etc.)
    
    Multi-Symbol Session Support:
    When a symbol is provided, heartbeats are managed per license+symbol,
    allowing multiple bot instances to maintain their own sessions.
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        device_fingerprint = data.get('device_fingerprint')
        symbol = data.get('symbol')  # MULTI-SYMBOL: Optional symbol for per-symbol sessions
        
        if not license_key:
            return jsonify({"status": "error", "message": "License key required"}), 400
        
        if not device_fingerprint:
            return jsonify({"status": "error", "message": "Device fingerprint required"}), 400
        
        # Rate limiting
        allowed, rate_msg = check_rate_limit(license_key, '/api/heartbeat')
        if not allowed:
            return jsonify({"status": "error", "message": rate_msg}), 429
        
        # Validate license
        is_valid, message, license_expiration = validate_license(license_key)
        if not is_valid:
            return jsonify({"status": "error", "message": message, "license_valid": False}), 403
        
        # Record heartbeat with session locking
        conn = get_db_connection()
        if conn:
            try:
                # MULTI-SYMBOL SESSION SUPPORT
                # When symbol is provided, use per-symbol session management
                if symbol and MULTI_SYMBOL_SESSIONS_ENABLED:
                    # Check for session conflict for this specific symbol
                    # For heartbeats, allow same device to continue
                    has_conflict, conflict_info = check_symbol_session_conflict(
                        conn, license_key, symbol, device_fingerprint, allow_same_device=True
                    )
                    
                    if has_conflict:
                        logging.warning(f"⚠️ Runtime session conflict for {license_key}/{symbol}: Device {device_fingerprint[:8]}... tried heartbeat while {conflict_info['device_fingerprint'][:8]}... is active")
                        return jsonify({
                            "status": "error",
                            "session_conflict": True,
                            "message": f"Symbol {symbol} already in use on another device",
                            "active_device": conflict_info['device_fingerprint'][:8] + "...",
                            "symbol": symbol
                        }), 403
                    
                    # Update session for this symbol
                    update_success = create_or_update_symbol_session(
                        conn, license_key, symbol, device_fingerprint,
                        metadata=data.get('metadata', {})
                    )
                    if update_success:
                        logging.info(f"✅ Heartbeat updated session timer for {license_key}/{symbol}")
                    
                    # Also insert into heartbeats table for history
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO heartbeats (license_key, bot_version, status, metadata)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            license_key,
                            data.get('bot_version', 'unknown'),
                            data.get('status', 'online'),
                            json.dumps(data.get('metadata', {}))
                        ))
                        conn.commit()
                    
                    active_count = count_active_symbol_sessions(conn, license_key)
                    
                    # Calculate days and hours until expiration
                    days_until_expiration = None
                    hours_until_expiration = None
                    if license_expiration:
                        now_utc = datetime.now(timezone.utc)
                        expiration = license_expiration
                        # If expiration is naive, make it UTC-aware
                        if expiration.tzinfo is None:
                            expiration = expiration.replace(tzinfo=timezone.utc)
                        time_until_expiration = expiration - now_utc
                        days_until_expiration = time_until_expiration.days
                        hours_until_expiration = time_until_expiration.total_seconds() / 3600
                    
                    # Get zones for this symbol
                    zones = get_zones_for_symbol(symbol)
                    
                    return jsonify({
                        "status": "success",
                        "message": f"Heartbeat recorded for {symbol}",
                        "license_valid": True,
                        "session_conflict": False,
                        "symbol": symbol,
                        "active_symbols": active_count,
                        "license_expiration": format_datetime_utc(license_expiration),
                        "days_until_expiration": days_until_expiration,
                        "hours_until_expiration": hours_until_expiration,
                        "zones": zones
                    }), 200
                
                # LEGACY: No symbol provided - use original single-session logic
                with conn.cursor() as cursor:
                    # Check for existing active session (last heartbeat within SESSION_TIMEOUT_SECONDS)
                    cursor.execute("""
                        SELECT device_fingerprint, last_heartbeat
                        FROM users
                        WHERE license_key = %s
                    """, (license_key,))
                    user = cursor.fetchone()
                    
                    if user:
                        stored_device = user[0]
                        last_heartbeat = user[1]
                        
                        # Check if another device is active (heartbeat within SESSION_TIMEOUT_SECONDS)
                        if stored_device and stored_device != device_fingerprint:
                            # Check if the stored device is still active
                            if last_heartbeat:
                                now_utc = datetime.now(timezone.utc)
                                heartbeat = last_heartbeat if last_heartbeat.tzinfo else last_heartbeat.replace(tzinfo=timezone.utc)
                                time_since_last = now_utc - heartbeat
                                if time_since_last < timedelta(seconds=SESSION_TIMEOUT_SECONDS):
                                    # SESSION CONFLICT: Another device is active
                                    logging.warning(f"⚠️ Runtime session conflict for {license_key}: Device {device_fingerprint[:8]}... tried heartbeat while {stored_device[:8]}... is active (last seen {int(time_since_last.total_seconds())}s ago)")
                                    return jsonify({
                                        "status": "error",
                                        "session_conflict": True,
                                        "message": "License already in use on another device",
                                        "active_device": stored_device[:8] + "..."  # Show partial for identification
                                    }), 403
                    
                    # No conflict - update heartbeat and device fingerprint
                    cursor.execute("""
                        UPDATE users 
                        SET last_heartbeat = NOW(),
                            device_fingerprint = %s,
                            metadata = %s
                        WHERE license_key = %s
                    """, (device_fingerprint, json.dumps(data.get('metadata', {})), license_key))
                    
                    # Also insert into heartbeats table for history (without device_fingerprint - column doesn't exist)
                    cursor.execute("""
                        INSERT INTO heartbeats (license_key, bot_version, status, metadata)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        license_key,
                        data.get('bot_version', 'unknown'),
                        data.get('status', 'online'),
                        json.dumps(data.get('metadata', {}))
                    ))
                    
                    conn.commit()
                    
                # Calculate days and hours until expiration
                days_until_expiration = None
                hours_until_expiration = None
                if license_expiration:
                    now_utc = datetime.now(timezone.utc)
                    expiration = license_expiration
                    # If expiration is naive, make it UTC-aware
                    if expiration.tzinfo is None:
                        expiration = expiration.replace(tzinfo=timezone.utc)
                    time_until_expiration = expiration - now_utc
                    days_until_expiration = time_until_expiration.days
                    hours_until_expiration = time_until_expiration.total_seconds() / 3600
                
                # Get zones for the configured symbol (if metadata contains symbol info)
                # For legacy mode without symbol parameter, try to get symbol from metadata
                metadata = data.get('metadata', {})
                symbol_for_zones = metadata.get('symbol')
                zones = get_zones_for_symbol(symbol_for_zones) if symbol_for_zones else []
                
                return jsonify({
                    "status": "success",
                    "message": "Heartbeat recorded",
                    "license_valid": True,
                    "session_conflict": False,
                    "license_expiration": license_expiration.isoformat() if license_expiration else None,
                    "days_until_expiration": days_until_expiration,
                    "hours_until_expiration": hours_until_expiration,
                    "zones": zones
                }), 200
            finally:
                return_connection(conn)
        
        return jsonify({"status": "error", "message": "Database error"}), 500
        
    except Exception as e:
        logging.error(f"Heartbeat error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/session/release', methods=['POST'])
def release_session():
    """
    Release session lock when bot shuts down.
    
    Parameters:
    - license_key: The license key
    - device_fingerprint: Device fingerprint
    - symbol: Trading symbol for multi-symbol session support (optional)
    
    Multi-Symbol Session Support:
    When a symbol is provided, only the session for that specific symbol is released,
    allowing other symbol sessions to continue running.
    """
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        device_fingerprint = data.get('device_fingerprint')
        symbol = data.get('symbol')  # MULTI-SYMBOL: Optional symbol for per-symbol sessions
        
        if not license_key:
            return jsonify({"status": "error", "message": "License key required"}), 400
        
        if not device_fingerprint:
            return jsonify({"status": "error", "message": "Device fingerprint required"}), 400
        
        # Validate license
        is_valid, message, _ = validate_license(license_key)
        if not is_valid:
            return jsonify({"status": "error", "message": message}), 403
        
        # Release session lock
        conn = get_db_connection()
        if conn:
            try:
                # MULTI-SYMBOL SESSION SUPPORT
                # When symbol is provided, release only the specific symbol session
                if symbol and MULTI_SYMBOL_SESSIONS_ENABLED:
                    released = release_symbol_session(conn, license_key, symbol, device_fingerprint)
                    
                    if released:
                        active_count = count_active_symbol_sessions(conn, license_key)
                        logging.info(f"✅ Session released for {license_key}/{symbol} from device {device_fingerprint[:8]}... ({active_count} active symbols remaining)")
                        return jsonify({
                            "status": "success",
                            "message": f"Session released for {symbol}",
                            "symbol": symbol,
                            "active_symbols": active_count
                        }), 200
                    else:
                        return jsonify({
                            "status": "info",
                            "message": f"No active session found for {symbol} on this device"
                        }), 200
                
                # LEGACY: No symbol provided - use original single-session logic
                with conn.cursor() as cursor:
                    # Only release if this device owns the session
                    cursor.execute("""
                        UPDATE users 
                        SET device_fingerprint = NULL,
                            last_heartbeat = NULL
                        WHERE license_key = %s 
                        AND device_fingerprint = %s
                    """, (license_key, device_fingerprint))
                    
                    rows_affected = cursor.rowcount
                    conn.commit()
                    
                    if rows_affected > 0:
                        logging.info(f"✅ Session released for {license_key} from device {device_fingerprint[:8]}...")
                        return jsonify({
                            "status": "success",
                            "message": "Session released successfully"
                        }), 200
                    else:
                        # Device doesn't own the session or session already released
                        return jsonify({
                            "status": "info",
                            "message": "No active session found for this device"
                        }), 200
            finally:
                return_connection(conn)
        
        return jsonify({"status": "error", "message": "Database error"}), 500
        
    except Exception as e:
        logging.error(f"Session release error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/session/clear', methods=['POST'])
def clear_stale_sessions():
    """Clear stale sessions (sessions older than SESSION_TIMEOUT_SECONDS)"""
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        
        if not license_key:
            return jsonify({"status": "error", "message": "License key required"}), 400
        
        # Validate license
        is_valid, message, _ = validate_license(license_key)
        if not is_valid:
            return jsonify({"status": "error", "message": message}), 403
        
        # Clear ONLY stale sessions (older than SESSION_TIMEOUT_SECONDS)
        # This prevents clearing active sessions and maintains session locking security
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # Only clear sessions that are truly stale (no heartbeat for 90+ seconds)
                    # This preserves session locking - active sessions are NOT cleared
                    cursor.execute("""
                        UPDATE users 
                        SET device_fingerprint = NULL,
                            last_heartbeat = NULL
                        WHERE license_key = %s
                        AND (last_heartbeat IS NULL OR last_heartbeat < NOW() - make_interval(secs => %s))
                    """, (license_key, SESSION_TIMEOUT_SECONDS))
                    
                    rows_affected = cursor.rowcount
                    conn.commit()
                    
                    if rows_affected > 0:
                        logging.info(f"✅ Cleared {rows_affected} stale session(s) for {license_key} (older than {SESSION_TIMEOUT_SECONDS}s)")
                    else:
                        logging.info(f"ℹ️ No stale sessions to clear for {license_key} (active session exists or already clear)")
                    
                    return jsonify({
                        "status": "success",
                        "message": "Stale sessions cleared" if rows_affected > 0 else "No stale sessions found",
                        "sessions_cleared": rows_affected
                    }), 200
            finally:
                return_connection(conn)
        
        return jsonify({"status": "error", "message": "Database error"}), 500
        
    except Exception as e:
        logging.error(f"Clear stale sessions error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/admin/force-clear-session', methods=['POST'])
def force_clear_session():
    """ADMIN ONLY: Force clear any session immediately (bypasses timeout check)"""
    try:
        data = request.get_json()
        license_key = data.get('license_key')
        admin_key = data.get('admin_key')
        
        # Require admin key
        if admin_key != ADMIN_API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized - admin key required"}), 403
        
        if not license_key:
            return jsonify({"status": "error", "message": "License key required"}), 400
        
        # Force clear session regardless of last_heartbeat
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE users 
                        SET device_fingerprint = NULL,
                            last_heartbeat = NULL
                        WHERE license_key = %s
                    """, (license_key,))
                    
                    rows_affected = cursor.rowcount
                    conn.commit()
                    
                    if rows_affected > 0:
                        logging.info(f"🔧 ADMIN: Force cleared session for {license_key}")
                    
                    return jsonify({
                        "status": "success",
                        "message": "Session force-cleared" if rows_affected > 0 else "No session found",
                        "sessions_cleared": rows_affected
                    }), 200
            finally:
                return_connection(conn)
        
        return jsonify({"status": "error", "message": "Database error"}), 500
        
    except Exception as e:
        logging.error(f"Force clear session error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/main', methods=['POST'])
def main():
    """Main signal processing endpoint with license validation and session locking"""
    try:
        data = request.get_json()
        
        # Validate license
        license_key = data.get('license_key')
        device_fingerprint = data.get('device_fingerprint')
        
        is_valid, message, expiration_date = validate_license(license_key)
        
        if not is_valid:
            return jsonify({
                "status": "error",
                "message": message,
                "license_valid": False,
                "license_expiration": expiration_date.isoformat() if expiration_date else None
            }), 403
        
        # Session locking - check if another device is using this license
        # NOTE: /api/main is used by launcher for validation ONLY - it does NOT create sessions
        # Only the bot creates sessions via /api/validate-license
        if device_fingerprint:
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Check for active sessions (do NOT clear or modify)
                        cursor.execute("""
                            SELECT device_fingerprint, last_heartbeat
                            FROM users
                            WHERE license_key = %s
                        """, (license_key,))
                        
                        user = cursor.fetchone()
                        
                        if user and user['device_fingerprint'] and user['last_heartbeat']:
                            # Check if any session exists (for info only, don't block launcher validation)
                            now_utc = datetime.now(timezone.utc)
                            heartbeat = user['last_heartbeat'] if user['last_heartbeat'].tzinfo else user['last_heartbeat'].replace(tzinfo=timezone.utc)
                            time_since_heartbeat = (now_utc - heartbeat).total_seconds()
                            
                            # Just log if session exists - launcher can still validate
                            # The actual blocking happens when bot tries to start via /api/validate-license
                            logging.info(f"ℹ️ /api/main - License {license_key} has existing session (device {user['device_fingerprint'][:8]}..., last seen {int(time_since_heartbeat)}s ago)")
                        
                        # DO NOT create or update session here - launcher is just validating
                        # Session creation happens when bot starts via /api/validate-license
                        
                finally:
                    return_connection(conn)
        
        # Process signal (cloud does not decide; bot decides locally)
        signal_type = data.get('signal_type', 'NEUTRAL')
        regime = data.get('regime', 'RANGING')
        vix_level = data.get('vix_level', 15.0)
        
        experiences = load_experiences()
        
        # Calculate days until expiration
        days_until_expiration = None
        hours_until_expiration = None
        if expiration_date:
            now_utc = datetime.now(timezone.utc)
            expiration = expiration_date
            # If expiration is naive, make it UTC-aware
            if expiration.tzinfo is None:
                expiration = expiration.replace(tzinfo=timezone.utc)
            time_until_expiration = expiration - now_utc
            days_until_expiration = time_until_expiration.days
            hours_until_expiration = time_until_expiration.total_seconds() / 3600
        
        response = {
            "status": "success",
            "license_valid": True,
            "message": message,
            "license_expiration": expiration_date.isoformat() if expiration_date else None,
            "days_until_expiration": days_until_expiration,
            "hours_until_expiration": hours_until_expiration,
            "experiences_used": len(experiences),
            "signal_type": signal_type,
            "regime": regime
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/admin/list-licenses', methods=['GET'])
def list_licenses():
    """List all licenses with details (admin only)"""
    try:
        # Verify admin API key
        api_key = request.headers.get('X-Admin-Key') or request.args.get('admin_key')
        if api_key != ADMIN_API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database error"}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        license_key, 
                        email, 
                        license_type, 
                        license_status, 
                        license_expiration,
                        created_at
                    FROM users 
                    ORDER BY created_at DESC
                """)
                licenses = cursor.fetchall()
                
                license_list = []
                for lic in licenses:
                    license_list.append({
                        "license_key": lic[0],
                        "email": lic[1],
                        "type": lic[2],
                        "status": lic[3],
                        "expires_at": lic[4].isoformat() if lic[4] else None,
                        "created_at": lic[5].isoformat() if lic[5] else None
                    })
                
                # Add admin key to the list
                license_list.insert(0, {
                    "license_key": ADMIN_API_KEY,
                    "email": "admin@quotrading.com",
                    "type": "ADMIN",
                    "status": "ACTIVE",
                    "expires_at": None,  # Never expires
                    "created_at": "2024-01-01T00:00:00"  # Static date
                })
                
                return jsonify({
                    "status": "success",
                    "total_licenses": len(license_list),
                    "licenses": license_list
                }), 200
                
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"Error listing licenses: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/update-license-status', methods=['POST'])
def update_license_status():
    """Update license status - ban/suspend/activate (admin only)"""
    try:
        data = request.get_json()
        
        # Verify admin API key
        api_key = request.headers.get('X-Admin-Key') or data.get('admin_key')
        if api_key != ADMIN_API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        license_key = data.get('license_key')
        new_status = data.get('status')  # 'active', 'suspended', 'expired', 'cancelled'
        
        if not license_key or not new_status:
            return jsonify({"status": "error", "message": "license_key and status required"}), 400
        
        if new_status not in ['active', 'suspended', 'expired', 'cancelled']:
            return jsonify({"status": "error", "message": "Invalid status"}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database error"}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET license_status = %s 
                    WHERE license_key = %s
                    RETURNING email, license_type
                """, (new_status, license_key))
                result = cursor.fetchone()
                conn.commit()
                
                if not result:
                    return jsonify({"status": "error", "message": "License not found"}), 404
                
                return jsonify({
                    "status": "success",
                    "message": f"License {license_key} status updated to {new_status}",
                    "email": result[0],
                    "license_type": result[1],
                    "new_status": new_status
                }), 200
                
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"Error updating license status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/admin/create-license', methods=['POST'])
def create_license():
    """Create a new license (admin only)
    
    Supports flexible duration:
    - minutes_valid: Duration in minutes (for testing short-lived licenses)
    - duration_days: Duration in days (default: 30)
    
    If minutes_valid is provided, it takes precedence over duration_days.
    """
    try:
        data = request.get_json()
        
        # Verify admin API key
        api_key = request.headers.get('X-Admin-Key') or data.get('admin_key')
        if api_key != ADMIN_API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        email = data.get('email')
        license_type = data.get('license_type', 'standard')
        
        # Support both minutes_valid and duration_days
        # minutes_valid takes precedence for testing short-lived licenses
        minutes_valid = data.get('minutes_valid')
        duration_days = data.get('duration_days', 30)
        
        if not email:
            return jsonify({"status": "error", "message": "Email required"}), 400
        
        license_key = generate_license_key()
        account_id = f"ACC-{secrets.token_hex(8).upper()}"
        
        # Calculate expiration based on provided duration
        if minutes_valid is not None:
            expiration = datetime.now(timezone.utc) + timedelta(minutes=int(minutes_valid))
            logging.info(f"Creating license with {minutes_valid} minutes validity (expires: {expiration})")
            duration_desc = f"{minutes_valid} minutes"
        else:
            expiration = datetime.now(timezone.utc) + timedelta(days=duration_days)
            logging.info(f"Creating license with {duration_days} days validity (expires: {expiration})")
            duration_desc = f"{duration_days} days"
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (account_id, license_key, email, license_type, license_status, license_expiration)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (account_id, license_key, email, license_type, 'active', expiration))
                conn.commit()
                
            return jsonify({
                "status": "success",
                "account_id": account_id,
                "license_key": license_key,
                "email": email,
                "license_type": license_type,
                "expires_at": expiration.isoformat(),
                "duration": duration_desc
            }), 201
            
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"Error creating license: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/whop/webhook', methods=['POST'])
def whop_webhook():
    """Handle Whop webhook events for subscription management"""
    try:
        payload = request.get_data()
        headers = request.headers
        
        # Verify signature if secret is set
        if WHOP_WEBHOOK_SECRET and 'X-Whop-Signature' in headers:
            signature = headers.get('X-Whop-Signature')
            expected_signature = hmac.new(
                WHOP_WEBHOOK_SECRET.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logging.warning("❌ Invalid Whop webhook signature")
                return jsonify({"status": "error", "message": "Invalid signature"}), 401
        
        payload = json.loads(payload)

        event_type = payload.get('action') # Whop often uses 'action' or 'type'
        if not event_type:
            event_type = payload.get('type')
            
        data = payload.get('data', {})
        
        logging.info(f"📬 Whop webhook: {event_type}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database error"}), 500
            
        try:
            with conn.cursor() as cursor:
                # Handle Membership Activated / Payment Succeeded
                if event_type in ['membership.activated', 'payment.succeeded']:
                    email = data.get('email') or data.get('user', {}).get('email')
                    membership_id = data.get('id')
                    user_id = data.get('user_id') or data.get('user', {}).get('id')
                    
                    if email:
                        # Check if user exists
                        cursor.execute("SELECT license_key FROM users WHERE email = %s", (email,))
                        existing = cursor.fetchone()
                        
                        if existing:
                            # Reactivate existing
                            cursor.execute("""
                                UPDATE users 
                                SET license_status = 'active', whop_membership_id = %s, whop_user_id = %s
                                WHERE email = %s
                            """, (membership_id, user_id, email))
                            license_key = existing[0]
                            logging.info(f"🔄 License reactivated for {mask_email(email)}")
                            log_webhook_event(event_type, 'success', membership_id, user_id, email, f'Reactivated license')
                        else:
                            # Create new license
                            license_key = generate_license_key()
                            account_id = f"ACC-{secrets.token_hex(8).upper()}"
                            cursor.execute("""
                                INSERT INTO users (account_id, license_key, email, license_type, license_status, whop_membership_id, whop_user_id)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (account_id, license_key, email, 'Monthly', 'active', membership_id, user_id))
                            logging.info(f"🎉 License created from Whop: {mask_sensitive(license_key)} for {mask_email(email)}")
                            log_webhook_event(event_type, 'success', membership_id, user_id, email, f'Created license {mask_sensitive(license_key)}')
                            
                            # Send email with Whop IDs
                            email_sent = send_license_email(email, license_key, user_id, membership_id)
                            if email_sent:
                                logging.info(f"✅ Email successfully sent to {mask_email(email)}")
                            else:
                                logging.error(f"❌ Email failed to send to {mask_email(email)}")
                        
                        
                        conn.commit()

                # Handle Membership Cancelled / Deactivated
                elif event_type in ['membership.cancelled', 'membership.deactivated', 'subscription.canceled']:
                    membership_id = data.get('id')
                    email = data.get('email') or data.get('user', {}).get('email')
                    
                    if membership_id:
                        # Get user email if not provided
                        if not email:
                            cursor.execute("SELECT email FROM users WHERE whop_membership_id = %s", (membership_id,))
                            result = cursor.fetchone()
                            if result:
                                email = result[0]
                        
                        cursor.execute("""
                            UPDATE users 
                            SET license_status = 'cancelled'
                            WHERE whop_membership_id = %s
                        """, (membership_id,))
                    elif email:
                        cursor.execute("""
                            UPDATE users 
                            SET license_status = 'cancelled'
                            WHERE email = %s
                        """, (email,))
                        
                    conn.commit()
                    logging.info(f"❌ License cancelled via Whop webhook")
                    
                    # Send cancellation email
                    if email:
                        cancellation_date = datetime.now().strftime("%B %d, %Y")
                        access_until = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
                        send_cancellation_email(email, cancellation_date, access_until, membership_id)

                # Handle Payment Failed
                elif event_type == 'payment.failed':
                    membership_id = data.get('membership_id') or data.get('id')
                    email = data.get('email') or data.get('user', {}).get('email')
                    
                    if membership_id:
                        # Get user email if not provided
                        if not email:
                            cursor.execute("SELECT email FROM users WHERE whop_membership_id = %s", (membership_id,))
                            result = cursor.fetchone()
                            if result:
                                email = result[0]
                        
                        cursor.execute("""
                            UPDATE users 
                            SET license_status = 'suspended'
                            WHERE whop_membership_id = %s
                        """, (membership_id,))
                        conn.commit()
                        logging.warning(f"⚠️ License suspended (payment failed)")
                        
                        # Send payment failed email
                        if email:
                            retry_date = (datetime.now() + timedelta(days=3)).strftime("%B %d, %Y")
                            send_payment_failed_email(email, retry_date, membership_id)
                
                # Handle Payment Succeeded (renewal)
                elif event_type in ['payment.succeeded', 'membership.renewed']:
                    membership_id = data.get('membership_id') or data.get('id')
                    email = data.get('email') or data.get('user', {}).get('email')
                    
                    if membership_id and email:
                        # Ensure license is active
                        cursor.execute("""
                            UPDATE users 
                            SET license_status = 'active'
                            WHERE whop_membership_id = %s
                        """, (membership_id,))
                        conn.commit()
                        
                        # Send renewal email
                        renewal_date = datetime.now().strftime("%B %d, %Y")
                        next_billing = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
                        send_renewal_email(email, renewal_date, next_billing, membership_id)
                        logging.info(f"✅ Renewal email sent to {mask_email(email)}")

        finally:
            return_connection(conn)
            
        return jsonify({"status": "success"}), 200

    except Exception as e:
        logging.error(f"Whop webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================================
# ADMIN DASHBOARD ENDPOINTS
# ============================================================================

@app.route('/api/admin/dashboard-stats', methods=['GET'])
def admin_dashboard_stats():
    """Get overall dashboard statistics"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Total users
            cursor.execute("SELECT COUNT(*) as total FROM users")
            total_users = cursor.fetchone()['total']
            
            # Active licenses
            cursor.execute("SELECT COUNT(*) as active FROM users WHERE license_status = 'ACTIVE'")
            active_licenses = cursor.fetchone()['active']
            
            # Online users (active in last 5 minutes based on API logs)
            cursor.execute("""
                SELECT COUNT(DISTINCT license_key) as online FROM api_logs
                WHERE created_at > NOW() - INTERVAL '5 minutes'
            """)
            online_users = cursor.fetchone()['online']
            
            # API calls in last 24 hours
            cursor.execute("""
                SELECT COUNT(*) as count FROM api_logs
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            api_calls_24h = cursor.fetchone()['count']
            
            # NOTE: Trade/experience analytics removed from dashboard stats.
            # Keeping these fields for backward compatibility with the admin UI.
            signal_exp_total = 0
            signal_exp_24h = 0
            total_trades = 0
            total_pnl = 0.0
            
            # Calculate revenue metrics
            pricing = {
                'MONTHLY': 200.00,
                'ANNUAL': 2000.00,
                'TRIAL': 0.00,
                'BETA': 0.00
            }
            
            # Get active subscriptions breakdown
            cursor.execute("""
                SELECT COUNT(*) as count, UPPER(license_type) as type
                FROM users
                WHERE UPPER(license_status) = 'ACTIVE'
                GROUP BY UPPER(license_type)
            """)
            active_breakdown = cursor.fetchall()
            
            # Calculate MRR (Monthly Recurring Revenue)
            mrr = sum(
                r['count'] * (pricing.get(r['type'], 0) if r['type'] == 'MONTHLY' 
                             else pricing.get(r['type'], 0) / 12) 
                for r in active_breakdown
            )
            
            # Calculate ARR (Annual Recurring Revenue)
            arr = mrr * 12
            
            return jsonify({
                "users": {
                    "total": total_users,
                    "active": active_licenses,
                    "online_now": online_users
                },
                "api_calls": {
                    "last_24h": api_calls_24h
                },
                "trades": {
                    "total": total_trades,
                    "total_pnl": total_pnl
                },
                "revenue": {
                    "mrr": round(mrr, 2),
                    "arr": round(arr, 2),
                    "active_subscriptions": active_breakdown
                }
            }), 200
    except Exception as e:
        logging.error(f"Dashboard stats error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    """List all users (same as list-licenses but formatted for dashboard)"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Primary query without any trade/experience tables.
            cursor.execute("""
                SELECT u.account_id, u.email, u.license_key, u.license_type, u.license_status,
                       u.license_expiration, u.created_at,
                       MAX(a.created_at) as last_active,
                       CASE WHEN MAX(a.created_at) > NOW() - INTERVAL '5 minutes'
                            THEN true ELSE false END as is_online,
                       COUNT(a.id) as api_call_count
                FROM users u
                LEFT JOIN api_logs a ON u.license_key = a.license_key
                GROUP BY u.account_id, u.email, u.license_key, u.license_type, u.license_status,
                         u.license_expiration, u.created_at
                ORDER BY u.created_at DESC
            """)
            users = cursor.fetchall()
            
            # Format for dashboard (use account_id instead of id for compatibility)
            formatted_users = []
            for user in users:
                formatted_users.append({
                    "account_id": user['account_id'],
                    "email": user['email'],
                    "license_key": user['license_key'],
                    "license_type": user['license_type'].upper() if user['license_type'] else 'MONTHLY',
                    "license_status": user['license_status'].upper() if user['license_status'] else 'ACTIVE',
                    "license_expiration": format_datetime_utc(user['license_expiration']),
                    "created_at": format_datetime_utc(user['created_at']),
                    "last_active": format_datetime_utc(user['last_active']),
                    "is_online": user['is_online'],
                    "api_call_count": int(user['api_call_count']) if user['api_call_count'] else 0,
                    "trade_count": 0
                })
            
            return jsonify({"users": formatted_users}), 200
    except Exception as e:
        logging.error(f"List users error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/user/<account_id>', methods=['GET'])
def admin_get_user(account_id):
    """Get detailed information about a specific user"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get user details with last active from api_logs
            cursor.execute("""
                SELECT u.account_id, u.email, u.license_key, u.license_type, u.license_status,
                       u.license_expiration, u.created_at,
                       MAX(a.created_at) as last_active
                FROM users u
                LEFT JOIN api_logs a ON u.license_key = a.license_key
                WHERE u.account_id = %s OR u.license_key = %s
                GROUP BY u.account_id, u.email, u.license_key, u.license_type, u.license_status,
                         u.license_expiration, u.created_at
            """, (account_id, account_id))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            # Get API call count for this user
            cursor.execute("""
                SELECT COUNT(*) as api_calls
                FROM api_logs
                WHERE license_key = %s
            """, (user['license_key'],))
            api_call_result = cursor.fetchone()
            api_call_count = api_call_result['api_calls'] if api_call_result else 0
            
            # Trade/experience statistics removed.
            trade_stats_result = None
            
            # Format user data
            user_data = {
                "user": {
                    "account_id": user['account_id'],
                    "email": user['email'],
                    "license_key": user['license_key'],
                    "license_type": user['license_type'],
                    "license_status": user['license_status'],
                    "license_expiration": format_datetime_utc(user['license_expiration']),
                    "created_at": format_datetime_utc(user['created_at']),
                    "last_active": format_datetime_utc(user['last_active']),
                    "notes": None
                },
                "recent_api_calls": api_call_count,
                "trade_stats": {
                    "total_trades": int(trade_stats_result['total_trades']) if trade_stats_result else 0,
                    "total_pnl": float(trade_stats_result['total_pnl']) if trade_stats_result else 0.0,
                    "avg_pnl": float(trade_stats_result['avg_pnl']) if trade_stats_result else 0.0,
                    "winning_trades": int(trade_stats_result['winning_trades']) if trade_stats_result else 0
                },
                "recent_activity": []
            }
            
            return jsonify(user_data), 200
    except Exception as e:
        logging.error(f"Get user error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/recent-activity', methods=['GET'])
def admin_recent_activity():
    """Get recent API activity"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = int(request.args.get('limit', 50))
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"activity": []}), 200
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    a.created_at as timestamp,
                    COALESCE(u.id::text, 'Unknown') as account_id,
                    a.endpoint,
                    'POST' as method,
                    a.status_code,
                    0 as response_time_ms,
                    '0.0.0.0' as ip_address
                FROM api_logs a
                LEFT JOIN users u ON a.license_key = u.license_key
                ORDER BY a.created_at DESC
                LIMIT %s
            """, (limit,))
            activity = cursor.fetchall()
            
            formatted_activity = []
            for act in activity:
                formatted_activity.append({
                    "timestamp": act['timestamp'].isoformat() if act['timestamp'] else None,
                    "account_id": act['account_id'],
                    "endpoint": act['endpoint'],
                    "method": act['method'],
                    "status_code": act['status_code'],
                    "response_time_ms": act['response_time_ms'],
                    "ip_address": act['ip_address']
                })
            
            return jsonify({"activity": formatted_activity}), 200
    except Exception as e:
        logging.error(f"Recent activity error: {e}")
        return jsonify({"activity": []}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/online-users', methods=['GET'])
def admin_online_users():
    """Get currently online users with real-time performance data"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"users": []}), 200
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get online users with latest heartbeat data
            cursor.execute("""
                SELECT u.account_id, u.email, u.license_key, u.license_type, 
                       u.last_heartbeat, u.metadata
                FROM users u
                WHERE u.last_heartbeat > NOW() - INTERVAL '2 minutes'
                AND UPPER(u.license_status) = 'ACTIVE'
                ORDER BY u.last_heartbeat DESC
            """)
            online = cursor.fetchall()
            
            formatted = []
            for user in online:
                metadata = user.get('metadata', {})
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                
                formatted.append({
                    "account_id": user['account_id'],
                    "email": user['email'],
                    "license_key": user['license_key'],
                    "license_type": user['license_type'],
                    "last_active": user['last_heartbeat'].isoformat() if user['last_heartbeat'] else None,
                    # Real-time performance from heartbeat metadata
                    "symbol": metadata.get('symbol', 'N/A'),
                    "session_pnl": metadata.get('session_pnl', 0),
                    "total_trades": metadata.get('total_trades', 0),
                    "winning_trades": metadata.get('winning_trades', 0),
                    "losing_trades": metadata.get('losing_trades', 0),
                    "win_rate": metadata.get('win_rate', 0),
                    "current_position": metadata.get('current_position', 0),
                    "position_pnl": metadata.get('position_pnl', 0),
                    "status": metadata.get('status', 'unknown'),
                    "shadow_mode": metadata.get('shadow_mode', False),
                    # License status indicators
                    "license_expired": metadata.get('license_expired', False),
                    "license_grace_period": metadata.get('license_grace_period', False),
                    "near_expiry_mode": metadata.get('near_expiry_mode', False),
                    "days_until_expiration": metadata.get('days_until_expiration'),
                    "hours_until_expiration": metadata.get('hours_until_expiration')
                })
            
            return jsonify({"users": formatted}), 200
    except Exception as e:
        logging.error(f"Online users error: {e}")
        return jsonify({"users": []}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/suspend-user/<account_id>', methods=['POST', 'PUT'])
def admin_suspend_user(account_id):
    """Suspend a user (same as update-license-status)"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET license_status = 'SUSPENDED'
                WHERE account_id = %s OR license_key = %s
                RETURNING license_key
            """, (account_id, account_id))
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                return jsonify({"status": "success", "message": "User suspended"}), 200
            else:
                return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logging.error(f"Suspend user error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/activate-user/<account_id>', methods=['POST', 'PUT'])
def admin_activate_user(account_id):
    """Activate a user"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users SET license_status = 'ACTIVE'
                WHERE account_id = %s OR license_key = %s
                RETURNING license_key
            """, (account_id, account_id))
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                return jsonify({"status": "success", "message": "User activated"}), 200
            else:
                return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logging.error(f"Activate user error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/extend-license/<account_id>', methods=['POST', 'PUT'])
def admin_extend_license(account_id):
    """Extend a user's license"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    days = int(request.args.get('days', 30))
    
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE users 
                SET license_expiration = COALESCE(license_expiration, NOW()) + INTERVAL '%s days'
                WHERE account_id = %s OR license_key = %s
                RETURNING license_key, license_expiration
            """, (days, account_id, account_id))
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                return jsonify({
                    "status": "success", 
                    "message": f"License extended by {days} days",
                    "new_expiration": result[1].isoformat() if result[1] else None
                }), 200
            else:
                return jsonify({"error": "User not found"}), 404
    except Exception as e:
        logging.error(f"Extend license error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/delete-user/<account_id>', methods=['DELETE'])
def admin_delete_user(account_id):
    """Permanently delete a user and all their data"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = None
    try:
        cursor = conn.cursor()
        
        # First check if user exists
        cursor.execute("SELECT account_id, email, license_key FROM users WHERE account_id = %s", (account_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        user_license_key = user[2]
        
        deleted_experiences = 0
        
        # Delete user's API logs
        cursor.execute("DELETE FROM api_logs WHERE license_key = %s", (user_license_key,))
        deleted_logs = cursor.rowcount
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE account_id = %s", (account_id,))
        
        conn.commit()
        
        logging.info(f"Admin deleted user: {account_id} (email: {user[1]}) - {deleted_logs} api logs")
        
        return jsonify({
            "status": "success",
            "message": f"User {account_id} permanently deleted",
            "deleted": {
                "account_id": account_id,
                "email": user[1],
                "api_logs": deleted_logs
            }
        }), 200
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Delete user error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)

@app.route('/api/admin/add-user', methods=['POST'])
def admin_add_user():
    """Create a new user (same as create-license but formatted for dashboard)
    
    Supports flexible duration:
    - minutes_valid: Duration in minutes (for testing short-lived licenses)
    - days_valid: Duration in days (default: 30)
    
    If minutes_valid is provided, it takes precedence over days_valid.
    """
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    email = data.get('email')
    license_type = data.get('license_type', 'MONTHLY')
    
    # Support both minutes_valid and days_valid
    # minutes_valid takes precedence for testing short-lived licenses
    minutes_valid = data.get('minutes_valid')
    days_valid = data.get('days_valid', 30)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        license_key = generate_license_key()
        account_id = f"user_{license_key[:8]}"
        
        # Calculate expiration based on provided duration
        if minutes_valid is not None:
            expiration = datetime.now(timezone.utc) + timedelta(minutes=int(minutes_valid))
            logging.info(f"Creating license with {minutes_valid} minutes validity (expires: {expiration})")
        else:
            expiration = datetime.now(timezone.utc) + timedelta(days=int(days_valid))
            logging.info(f"Creating license with {days_valid} days validity (expires: {expiration})")
        
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (account_id, email, license_key, license_type, license_status, license_expiration)
                VALUES (%s, %s, %s, %s, 'ACTIVE', %s)
                RETURNING license_key
            """, (account_id, email, license_key, license_type, expiration))
            conn.commit()
            
            return jsonify({
                "status": "success",
                "license_key": license_key,
                "account_id": account_id,
                "email": email,
                "expires_at": format_datetime_utc(expiration),
                "expiration": format_datetime_utc(expiration)  # Keep for backward compatibility
            }), 201
    except Exception as e:
        logging.error(f"Add user error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)

@app.route('/api/admin/send-license-email', methods=['POST'])
def admin_send_license_email():
    """Send a license key via email"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    email = data.get('email')
    license_key = data.get('license_key')
    
    logging.info(f"📧 Send email request - email: {mask_email(email)}, license_key: {mask_sensitive(license_key)}")
    
    if not email or not license_key:
        return jsonify({"error": "Email and license_key are required"}), 400
    
    try:
        success = send_license_email(email, license_key)
        if success:
            return jsonify({"status": "success", "message": "Email sent successfully"}), 200
        else:
            return jsonify({"error": "Failed to send email"}), 500
    except Exception as e:
        logging.error(f"Send email error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# END ADMIN DASHBOARD ENDPOINTS
# ============================================================================

@app.route('/api/admin/expire-licenses', methods=['POST'])
def expire_licenses():
    """Manually trigger license expiration check (can be called by cron/scheduler)"""
    try:
        api_key = request.headers.get('X-Admin-Key')
        if api_key != ADMIN_API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database error"}), 500
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET license_status = 'expired'
                    WHERE license_expiration < NOW() 
                    AND license_status = 'active'
                    RETURNING license_key, email
                """)
                expired = cursor.fetchall()
                conn.commit()
                
                return jsonify({
                    "status": "success",
                    "expired_count": len(expired),
                    "expired_licenses": [row[0] for row in expired]
                }), 200
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"Error expiring licenses: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================================
# Deprecated analytics section
# ============================================================================
# NOTE: This service no longer exposes trade-scoring analytics.

@app.route('/api/profile', methods=['GET'])
def get_user_profile():
    """
    Get user profile information (self-service)
    Users can view their own account details and trading statistics
    
    Authentication: License key via query parameter or Authorization header
    ?license_key=LIC-KEY-123 OR Authorization: Bearer LIC-KEY-123
    
    Response:
    {
        "status": "success",
        "profile": {
            "account_id": "ACC123",
            "email": "us***@example.com",  // Masked for security
            "license_type": "Monthly",
            "license_status": "active",
            "license_expiration": "2025-12-31T23:59:59",
            "days_until_expiration": 27,
            "created_at": "2025-01-01T00:00:00",
            "account_age_days": 337,
            "last_active": "2025-12-04T20:00:00",
            "is_online": true
        },
        "trading_stats": {
            "total_trades": 150,
            "total_pnl": 5420.50,
            "avg_pnl_per_trade": 36.14,
            "winning_trades": 95,
            "losing_trades": 55,
            "win_rate_percent": 63.33,
            "best_trade": 250.00,
            "worst_trade": -180.00
        },
        "recent_activity": {
            "api_calls_today": 45,
            "api_calls_total": 1234,
            "last_heartbeat": "2025-12-04T20:30:00",
            "current_device": "abc123...",
            "symbols_traded": ["ES", "NQ", "YM"]
        }
    }
    """
    try:
        # Get license key from query parameter or Authorization header
        license_key = request.args.get('license_key')
        if not license_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                license_key = auth_header.replace('Bearer ', '').strip()
        
        if not license_key:
            return jsonify({"error": "License key required. Use ?license_key=KEY or Authorization: Bearer KEY"}), 400
        
        # Rate limiting to prevent abuse (global limit of 100 requests per minute)
        allowed, rate_msg = check_rate_limit(license_key, '/api/profile')
        if not allowed:
            logging.warning(f"⚠️ Rate limit exceeded for /api/profile: {mask_sensitive(license_key)}")
            return jsonify({"error": rate_msg}), 429
        
        # Validate license key (returns is_valid, message, expiration_datetime)
        is_valid, msg, _ = validate_license(license_key)
        if not is_valid:
            logging.warning(f"⚠️ Invalid license key in /api/profile: {mask_sensitive(license_key)}")
            return jsonify({"error": "Invalid license key"}), 401
        
        # Get database connection to check user status
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # 1. Get user profile details and check status
                cursor.execute("""
                    SELECT account_id, email, license_type, license_status,
                           license_expiration, created_at, last_heartbeat,
                           device_fingerprint
                    FROM users
                    WHERE license_key = %s
                """, (license_key,))
                user = cursor.fetchone()
                
                if not user:
                    return jsonify({"error": "User not found"}), 404
                
                # Check if account is suspended
                if user['license_status'].upper() == 'SUSPENDED':
                    logging.warning(f"⚠️ Suspended account tried to access profile: {mask_sensitive(license_key)}")
                    return jsonify({"error": "Account suspended. Contact support."}), 403
                
                # 2. Trade analytics removed
                trade_stats = {
                    "total_trades": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                }
                
                # 3. Get API call statistics
                cursor.execute("""
                    SELECT COUNT(*) as api_calls_total
                    FROM api_logs
                    WHERE license_key = %s
                """, (license_key,))
                api_stats = cursor.fetchone()
                
                # 4. Get today's API calls
                cursor.execute("""
                    SELECT COUNT(*) as api_calls_today
                    FROM api_logs
                    WHERE license_key = %s 
                      AND created_at >= CURRENT_DATE
                """, (license_key,))
                api_today = cursor.fetchone()
                
                # 5. Symbols traded removed
                symbols_list = []
                
                # Calculate derived fields
                now = datetime.now(timezone.utc)
                
                # Days until expiration
                days_until_expiration = None
                if user['license_expiration']:
                    if user['license_expiration'].tzinfo is None:
                        expiration = user['license_expiration'].replace(tzinfo=timezone.utc)
                    else:
                        expiration = user['license_expiration']
                    days_until_expiration = (expiration - now).days
                
                # Account age
                account_age_days = None
                if user['created_at']:
                    if user['created_at'].tzinfo is None:
                        created = user['created_at'].replace(tzinfo=timezone.utc)
                    else:
                        created = user['created_at']
                    account_age_days = (now - created).days
                
                # Online status (heartbeat within last 2 minutes)
                is_online = False
                if user['last_heartbeat']:
                    if user['last_heartbeat'].tzinfo is None:
                        last_hb = user['last_heartbeat'].replace(tzinfo=timezone.utc)
                    else:
                        last_hb = user['last_heartbeat']
                    time_since_heartbeat = (now - last_hb).total_seconds()
                    is_online = time_since_heartbeat < 120  # 2 minutes
                
                # Win rate calculation
                total_trades = int(trade_stats['total_trades']) if trade_stats['total_trades'] else 0
                winning_trades = int(trade_stats['winning_trades']) if trade_stats['winning_trades'] else 0
                win_rate_percent = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
                
                # Extract values for reuse
                total_pnl = float(trade_stats['total_pnl']) if trade_stats['total_pnl'] else 0.0
                device_fp = user.get('device_fingerprint', '')
                device_display = device_fp[:8] + '...' if len(device_fp) > 8 else device_fp or None
                
                # Build response
                profile_data = {
                    "status": "success",
                    "profile": {
                        "account_id": user['account_id'],
                        "email": mask_email(user['email']) if user['email'] else None,
                        "license_type": user['license_type'],
                        "license_status": user['license_status'],
                        "license_expiration": user['license_expiration'].isoformat() if user['license_expiration'] else None,
                        "days_until_expiration": days_until_expiration,
                        "created_at": user['created_at'].isoformat() if user['created_at'] else None,
                        "account_age_days": account_age_days,
                        "last_active": user['last_heartbeat'].isoformat() if user['last_heartbeat'] else None,
                        "is_online": is_online
                    },
                    "trading_stats": {
                        "total_trades": total_trades,
                        "total_pnl": total_pnl,
                        "avg_pnl_per_trade": float(trade_stats['avg_pnl']) if trade_stats['avg_pnl'] else 0.0,
                        "winning_trades": winning_trades,
                        "losing_trades": int(trade_stats['losing_trades']) if trade_stats['losing_trades'] else 0,
                        "win_rate_percent": round(win_rate_percent, 2),
                        "best_trade": float(trade_stats['best_trade']) if trade_stats['best_trade'] else 0.0,
                        "worst_trade": float(trade_stats['worst_trade']) if trade_stats['worst_trade'] else 0.0
                    },
                    "recent_activity": {
                        "api_calls_today": int(api_today['api_calls_today']) if api_today['api_calls_today'] else 0,
                        "api_calls_total": int(api_stats['api_calls_total']) if api_stats['api_calls_total'] else 0,
                        "last_heartbeat": user['last_heartbeat'].isoformat() if user['last_heartbeat'] else None,
                        "current_device": device_display,
                        "symbols_traded": symbols_list
                    }
                }
                
                logging.info(f"✅ Profile accessed: {mask_email(user['email'])}, {total_trades} trades, ${total_pnl:.2f} PnL")
                return jsonify(profile_data), 200
                
        except Exception as e:
            logging.error(f"Profile query error: {e}")
            return jsonify({"error": "Failed to retrieve profile data"}), 500
        finally:
            return_connection(conn)
            
    except Exception as e:
        logging.error(f"Profile endpoint error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# END USER PROFILE ENDPOINT
# ============================================================================

# ============================================================================
# ADMIN/STATS ENDPOINTS
# ============================================================================

@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        "status": "success",
        "message": "QuoTrading API",
        "endpoints": ["/api/hello", "/api/main", "/api/profile", "/api/whop/webhook", "/api/admin/create-license", "/api/admin/expire-licenses"]
    }), 200

# ========== PHASE 2: CHART DATA ENDPOINTS ==========

@app.route('/api/admin/charts/user-growth', methods=['GET'])
def admin_chart_user_growth():
    """Get user growth by week for last 12 weeks"""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"weeks": [], "counts": []}), 200
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('week', created_at) as week,
                    COUNT(*) as count
                FROM users
                WHERE created_at >= NOW() - INTERVAL '12 weeks'
                GROUP BY week
                ORDER BY week
            """)
            results = cursor.fetchall()
            
            weeks = [f"Week {i+1}" for i in range(len(results))]
            counts = [int(r['count']) for r in results]
            
            return jsonify({"weeks": weeks, "counts": counts}), 200
    except Exception as e:
        logging.error(f"User growth chart error: {e}")
        return jsonify({"weeks": [], "counts": []}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/charts/api-usage', methods=['GET'])
def admin_chart_api_usage():
    """Get API calls per hour for last 24 hours"""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"hours": [], "counts": []}), 200
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    EXTRACT(HOUR FROM timestamp) as hour,
                    COUNT(*) as count
                FROM api_logs
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY hour
                ORDER BY hour
            """)
            results = cursor.fetchall()
            
            # Create 24-hour array with 0 for missing hours
            hour_counts = {int(r['hour']): int(r['count']) for r in results}
            hours = [f"{h:02d}:00" for h in range(24)]
            counts = [hour_counts.get(h, 0) for h in range(24)]
            
            return jsonify({"hours": hours, "counts": counts}), 200
    except Exception as e:
        logging.error(f"API usage chart error: {e}")
        return jsonify({"hours": [], "counts": []}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/charts/mrr', methods=['GET'])
def admin_chart_mrr():
    """Get Monthly Recurring Revenue trend"""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"months": [], "revenue": []}), 200
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    TO_CHAR(DATE_TRUNC('month', created_at), 'Mon') as month,
                    COUNT(*) FILTER (WHERE license_type = 'MONTHLY') * 200.00 +
                    COUNT(*) FILTER (WHERE license_type = 'ANNUAL') * 2000.00 as revenue
                FROM users
                WHERE created_at >= NOW() - INTERVAL '6 months'
                AND UPPER(license_status) = 'ACTIVE'
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY DATE_TRUNC('month', created_at)
            """)
            results = cursor.fetchall()
            
            months = [r['month'] for r in results]
            revenue = [float(r['revenue']) if r['revenue'] else 0 for r in results]
            
            return jsonify({"months": months, "revenue": revenue}), 200
    except Exception as e:
        logging.error(f"MRR chart error: {e}")
        return jsonify({"months": [], "revenue": []}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/charts/collective-pnl', methods=['GET'])
def admin_chart_collective_pnl():
    """Deprecated: trade analytics removed."""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({"dates": [], "pnl": []}), 200

@app.route('/api/admin/charts/win-rate-trend', methods=['GET'])
def admin_chart_win_rate_trend():
    """Deprecated: trade analytics removed."""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({"weeks": [], "win_rates": []}), 200

@app.route('/api/admin/charts/top-performers', methods=['GET'])
def admin_chart_top_performers():
    """Deprecated: trade analytics removed."""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({"users": [], "pnl": []}), 200

@app.route('/api/admin/charts/experience-growth', methods=['GET'])
def admin_chart_experience_growth():
    """Deprecated: trade analytics removed."""
    admin_key = request.args.get('admin_key') or request.args.get('license_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({"dates": [], "counts": []}), 200

@app.route('/api/admin/charts/confidence-dist', methods=['GET'])
@app.route('/api/admin/charts/score-dist', methods=['GET'])
def admin_chart_score_dist():
    """Deprecated."""
    return jsonify({"ranges": [], "counts": []}), 200

@app.route('/api/admin/charts/confidence-winrate', methods=['GET'])
@app.route('/api/admin/charts/score-winrate', methods=['GET'])
def admin_chart_score_winrate():
    """Deprecated."""
    return jsonify({"score": [], "win_rate": [], "sample_size": []}), 200

# ==================== REPORTS ENDPOINTS ====================

@app.route('/api/admin/reports/user-activity', methods=['GET'])
def admin_report_user_activity():
    """Generate user activity report with date range filters"""
    auth_header = request.headers.get('X-API-Key')
    if auth_header != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    license_type = request.args.get('license_type', 'all')
    status = request.args.get('status', 'all')
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        query = """
            SELECT 
                l.account_id,
                l.email,
                l.created_at,
                l.last_active,
                l.license_type,
                l.license_status,
                COUNT(DISTINCT a.id) as api_calls,
                COUNT(DISTINCT r.id) FILTER (WHERE r.took_trade = TRUE) as trades,
                COALESCE(SUM(r.pnl), 0) as total_pnl
            FROM users l
            LEFT JOIN api_logs a ON l.license_key = a.license_key
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND l.created_at >= %s"
            params.append(start_date)
        if end_date:
            query += " AND l.created_at <= %s"
            params.append(end_date)
        if license_type != 'all':
            query += " AND UPPER(l.license_type) = UPPER(%s)"
            params.append(license_type)
        if status != 'all':
            query += " AND UPPER(l.license_status) = UPPER(%s)"
            params.append(status)
        
        query += " GROUP BY l.account_id, l.email, l.created_at, l.last_active, l.license_type, l.license_status"
        query += " ORDER BY l.created_at DESC LIMIT 500"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append({
                "account_id": r['account_id'][:8] + "..." if r['account_id'] else "N/A",
                "email": r['email'],
                "signup_date": r['created_at'].strftime('%Y-%m-%d') if r['created_at'] else "N/A",
                "last_active": r['last_active'].strftime('%Y-%m-%d %H:%M') if r['last_active'] else "Never",
                "license_type": r['license_type'],
                "status": r['license_status'],
                "api_calls": int(r['api_calls']),
                "trades": int(r['trades']),
                "total_pnl": round(float(r['total_pnl']), 2)
            })
        
        return jsonify({"data": formatted_results, "count": len(formatted_results)}), 200
    except Exception as e:
        logging.error(f"User activity report error: {e}")
        return jsonify({"error": str(e), "data": [], "count": 0}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/reports/revenue', methods=['GET'])
def admin_report_revenue():
    """Generate revenue analysis report"""
    auth_header = request.headers.get('X-API-Key')
    if auth_header != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    month = request.args.get('month', str(datetime.now().month))
    year = request.args.get('year', str(datetime.now().year))
    license_type_filter = request.args.get('license_type', 'all')
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Define pricing
        pricing = {
            'MONTHLY': 200.00,
            'ANNUAL': 2000.00,
            'TRIAL': 0.00
        }
        
        # Get new subscriptions
        query_new = """
            SELECT COUNT(*) as count, UPPER(license_type) as type
            FROM users
            WHERE EXTRACT(MONTH FROM created_at) = %s
              AND EXTRACT(YEAR FROM created_at) = %s
        """
        params = [int(month), int(year)]
        
        if license_type_filter != 'all':
            query_new += " AND UPPER(license_type) = UPPER(%s)"
            params.append(license_type_filter)
        
        query_new += " GROUP BY UPPER(license_type)"
        cursor.execute(query_new, params)
        new_subs = cursor.fetchall()
        
        # Calculate metrics
        new_count = sum(r['count'] for r in new_subs)
        new_revenue = sum(r['count'] * pricing.get(r['type'], 0) for r in new_subs)
        
        # Get active users
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM users
            WHERE UPPER(license_status) = 'ACTIVE'
        """)
        active_users = cursor.fetchone()['count']
        
        # Get expired this month
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM users
            WHERE license_expiration >= %s
              AND license_expiration < %s
              AND EXTRACT(MONTH FROM license_expiration) = %s
              AND EXTRACT(YEAR FROM license_expiration) = %s
        """, [
            f"{year}-{month}-01",
            f"{year}-{int(month)+1 if int(month) < 12 else 1}-01",
            int(month),
            int(year)
        ])
        expired = cursor.fetchone()['count']
        
        # Calculate MRR (all active monthly licenses)
        cursor.execute("""
            SELECT COUNT(*) as count, UPPER(license_type) as type
            FROM users
            WHERE UPPER(license_status) = 'ACTIVE'
            GROUP BY UPPER(license_type)
        """)
        active_breakdown = cursor.fetchall()
        
        mrr = sum(r['count'] * (pricing.get(r['type'], 0) if r['type'] == 'MONTHLY' else pricing.get(r['type'], 0) / 12) for r in active_breakdown)
        arpu = mrr / active_users if active_users > 0 else 0
        churn_rate = (expired / active_users * 100) if active_users > 0 else 0
        
        return jsonify({
            "new_subscriptions": new_count,
            "new_revenue": round(new_revenue, 2),
            "renewals": 0,  # Would need renewal tracking
            "renewal_revenue": 0.00,
            "cancellations": expired,
            "lost_revenue": round(expired * 200.00, 2),  # Estimate
            "net_mrr": round(mrr, 2),
            "churn_rate": round(churn_rate, 2),
            "arpu": round(arpu, 2),
            "active_users": active_users
        }), 200
    except Exception as e:
        logging.error(f"Revenue report error: {e}")
        return jsonify({"error": str(e)}), 200
    finally:
        return_connection(conn)

@app.route('/api/admin/reports/performance', methods=['GET'])
def admin_report_performance():
    """Generate trading performance report"""
    auth_header = request.headers.get('X-API-Key')
    if auth_header != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    symbol = request.args.get('symbol', 'all')
    
    return jsonify({
        "total_trades": 0,
        "win_rate": 0,
        "total_pnl": 0,
        "avg_score": 0,
        "avg_confidence": 0,
        "avg_duration_minutes": 0,
        "best_day": {"date": "N/A", "pnl": 0},
        "worst_day": {"date": "N/A", "pnl": 0}
    }), 200

@app.route('/api/admin/reports/retention', methods=['GET'])
def admin_report_retention():
    """Generate retention and churn report"""
    auth_header = request.headers.get('X-API-Key')
    if auth_header != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Current active users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE UPPER(license_status) = 'ACTIVE'")
        active_users = cursor.fetchone()['count']
        
        # Expired this month
        cursor.execute("""
            SELECT COUNT(*) as count FROM users
            WHERE license_expiration >= DATE_TRUNC('month', NOW())
              AND license_expiration < DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
        """)
        expired_this_month = cursor.fetchone()['count']
        
        # Average subscription length
        cursor.execute("""
            SELECT AVG(EXTRACT(DAY FROM license_expiration - created_at)) as avg_days
            FROM users
            WHERE license_expiration IS NOT NULL
        """)
        avg_length = cursor.fetchone()['avg_days']
        
        # Cohort analysis - users by signup month
        cursor.execute("""
            SELECT 
                TO_CHAR(created_at, 'YYYY-MM') as cohort_month,
                COUNT(*) as users,
                COUNT(*) FILTER (WHERE UPPER(license_status) = 'ACTIVE') as still_active
            FROM users
            WHERE created_at >= NOW() - INTERVAL '12 months'
            GROUP BY TO_CHAR(created_at, 'YYYY-MM')
            ORDER BY cohort_month DESC
            LIMIT 12
        """)
        cohorts = cursor.fetchall()
        
        # Calculate metrics
        renewals = active_users - expired_this_month if active_users > 0 else 0
        retention_rate = (renewals / active_users * 100) if active_users > 0 else 0
        churn_rate = (expired_this_month / active_users * 100) if active_users > 0 else 0
        
        # Lifetime value (average)
        ltv = (avg_length / 30 * 200.00) if avg_length else 0
        
        cohort_data = []
        for c in cohorts:
            retention = (c['still_active'] / c['users'] * 100) if c['users'] > 0 else 0
            cohort_data.append({
                "month": c['cohort_month'],
                "users": c['users'],
                "still_active": c['still_active'],
                "retention": round(retention, 2)
            })
        
        return jsonify({
            "active_users": active_users,
            "expired_this_month": expired_this_month,
            "renewals": renewals,
            "retention_rate": round(retention_rate, 2),
            "churn_rate": round(churn_rate, 2),
            "avg_subscription_days": round(float(avg_length), 2) if avg_length else 0,
            "lifetime_value": round(ltv, 2),
            "cohorts": cohort_data
        }), 200
    except Exception as e:
        logging.error(f"Retention report error: {e}")
        return jsonify({"error": str(e)}), 200
    finally:
        return_connection(conn)

def init_database_if_needed():
    """Initialize required database tables/indexes if they don't exist."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode='require'
        )
        cursor = conn.cursor()
        
        # NOTE: This service no longer manages or requires any trade/experience tables.
        
        conn.commit()
        cursor.close()
        return_connection(conn)
        
        app.logger.info("✅ PostgreSQL database initialized successfully")
        
    except Exception as e:
        app.logger.warning(f"Database initialization check: {e}")

@app.route('/api/health', methods=['GET'])
def health_check():
    """Public health check endpoint for server infrastructure monitoring"""
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "unknown",
        "flask_server": {"status": "healthy", "version": "2.0", "environment": "production", "region": "West US 2"},
        "app_service_plan": {"status": "healthy", "name": "quotrading-asp", "tier": "Basic", "region": "West US 2"},
        "database": {"status": "unknown", "response_time_ms": 0, "pool_available": 0, "pool_used": 0, "error": None},
        "email_service": {"status": "unknown", "provider": "sendgrid" if SENDGRID_API_KEY else "smtp", "error": None},
        "whop_api": {"status": "unknown", "response_time_ms": 0, "error": None}
    }
    
    # Check PostgreSQL connection + pool stats
    db_start = datetime.now()
    try:
        conn = get_db_connection()
        if conn:
            # Test query
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT 1 as test")
                cursor.fetchone()
            
            return_connection(conn)
            db_time = (datetime.now() - db_start).total_seconds() * 1000
            
            # Get pool stats if available
            pool_available = 0
            pool_used = 0
            if _db_pool:
                try:
                    # SimpleConnectionPool doesn't expose stats directly, but we can infer
                    pool_available = _db_pool.maxconn - len(getattr(_db_pool, '_used', {}))
                    pool_used = len(getattr(_db_pool, '_used', {}))
                except:
                    pass
            
            health_status["database"] = {
                "status": "healthy",
                "response_time_ms": round(db_time, 2),
                "pool_available": pool_available,
                "pool_used": pool_used,
                "error": None
            }
        else:
            health_status["database"] = {
                "status": "unhealthy",
                "response_time_ms": 0,
                "pool_available": 0,
                "pool_used": 0,
                "error": "Database connection failed"
            }
    except Exception as e:
        logging.error(f"Database health check error: {e}")
        health_status["database"] = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "pool_available": 0,
            "pool_used": 0,
            "error": str(e)
        }
    
    # Check email service
    try:
        if SENDGRID_API_KEY:
            # SendGrid API check - verify API key format
            if len(SENDGRID_API_KEY) > 20 and SENDGRID_API_KEY.startswith('SG.'):
                health_status["email_service"] = {
                    "status": "healthy",
                    "provider": "sendgrid",
                    "error": None
                }
            else:
                health_status["email_service"] = {
                    "status": "degraded",
                    "provider": "sendgrid",
                    "error": "API key format invalid"
                }
        elif SMTP_USERNAME and SMTP_PASSWORD:
            # SMTP configured
            health_status["email_service"] = {
                "status": "healthy",
                "provider": "smtp",
                "error": None
            }
        else:
            health_status["email_service"] = {
                "status": "unhealthy",
                "provider": "none",
                "error": "No email service configured"
            }
    except Exception as e:
        health_status["email_service"] = {
            "status": "unhealthy",
            "provider": "unknown",
            "error": str(e)
        }
    
    # Check Whop API connectivity
    whop_start = datetime.now()
    try:
        if WHOP_API_KEY:
            # Ping Whop API base URL to check connectivity
            response = requests.get(
                "https://api.whop.com",
                timeout=5
            )
            whop_time = (datetime.now() - whop_start).total_seconds() * 1000
            
            # If we can reach Whop and have a key configured, mark as healthy
            if response.status_code in [200, 404]:  # 404 is expected for base URL
                health_status["whop_api"] = {
                    "status": "healthy",
                    "response_time_ms": round(whop_time, 2),
                    "error": None
                }
            else:
                health_status["whop_api"] = {
                    "status": "degraded",
                    "response_time_ms": round(whop_time, 2),
                    "error": f"HTTP {response.status_code}"
                }
        else:
            health_status["whop_api"] = {
                "status": "degraded",
                "response_time_ms": 0,
                "error": "Whop API key not configured"
            }
    except requests.Timeout:
        health_status["whop_api"] = {
            "status": "unhealthy",
            "response_time_ms": 5000,
            "error": "Request timeout"
        }
    except Exception as e:
        health_status["whop_api"] = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "error": str(e)
        }
    
    # Determine overall health
    statuses = [
        health_status["flask_server"]["status"],
        health_status["app_service_plan"]["status"],
        health_status["database"]["status"],
        health_status["email_service"]["status"],
        health_status["whop_api"]["status"]
    ]
    
    if all(s == "healthy" for s in statuses):
        health_status["overall_status"] = "healthy"
    elif any(s == "unhealthy" for s in statuses):
        health_status["overall_status"] = "unhealthy"
    else:
        health_status["overall_status"] = "degraded"
    
    # Return 200 if healthy, 503 if unhealthy, 200 if degraded
    status_code = 200 if health_status["overall_status"] != "unhealthy" else 503
    return jsonify(health_status), status_code

@app.route('/api/admin/system-health', methods=['GET'])
def admin_system_health():
    """Get detailed system health status with admin authentication"""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get basic health status
    basic_health = health_check()
    health_data = basic_health[0].get_json()
    
    # Add admin-only metrics
    db_start = datetime.now()
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get active license count
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE license_status = 'ACTIVE'")
                result = cursor.fetchone()
                active_licenses = result['count'] if result else 0
                
            return_connection(conn)
            db_time = (datetime.now() - db_start).total_seconds() * 1000
            
            health_data["trade_analytics"] = {
                "status": "disabled",
                "total_trades": 0,
                "response_time_ms": round(db_time, 2),
                "error": None
            }
            health_data["licenses"] = {
                "active_count": active_licenses
            }
        else:
            health_data["trade_analytics"] = {
                "status": "disabled",
                "total_trades": 0,
                "response_time_ms": 0,
                "error": "Database unavailable"
            }
    except Exception as e:
        logging.error(f"Admin health check error: {e}")
        health_data["trade_analytics"] = {
            "status": "disabled",
            "total_trades": 0,
            "response_time_ms": 0,
            "error": str(e)
        }
    
    return jsonify(health_data), 200

# ============================================================================
# BULK OPERATIONS ENDPOINTS
# ============================================================================

@app.route('/api/admin/bulk/extend', methods=['POST'])
def admin_bulk_extend():
    """Extend licenses for multiple users"""
    api_key = request.headers.get('X-Admin-API-Key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    license_keys = data.get('license_keys', [])
    days = data.get('days', 30)
    
    if not license_keys:
        return jsonify({"error": "No license keys provided"}), 400
    
    if len(license_keys) > 100:
        return jsonify({"error": "Maximum 100 users per bulk operation"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    success_count = 0
    failed_count = 0
    errors = []
    
    try:
        for key in license_keys:
            try:
                cur.execute("""
                    UPDATE users 
                    SET license_expiration = license_expiration + INTERVAL '%s days'
                    WHERE license_key = %s
                """, (days, key))
                if cur.rowcount > 0:
                    success_count += 1
                else:
                    failed_count += 1
                    errors.append(f"{key[:8]}... not found")
            except Exception as e:
                failed_count += 1
                errors.append(f"{key[:8]}...: {str(e)}")
        
        conn.commit()
        logging.info(f"Bulk extend: {success_count} succeeded, {failed_count} failed")
    except Exception as e:
        conn.rollback()
        logging.error(f"Bulk extend error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)
    
    return jsonify({
        "success": success_count,
        "failed": failed_count,
        "errors": errors[:10]  # Limit error list
    }), 200

@app.route('/api/admin/bulk/suspend', methods=['POST'])
def admin_bulk_suspend():
    """Suspend multiple user licenses"""
    api_key = request.headers.get('X-Admin-API-Key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    license_keys = data.get('license_keys', [])
    
    if not license_keys or len(license_keys) > 100:
        return jsonify({"error": "Invalid request"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE users 
            SET license_status = 'SUSPENDED'
            WHERE license_key = ANY(%s)
        """, (license_keys,))
        success_count = cur.rowcount
        conn.commit()
        logging.info(f"Bulk suspended {success_count} users")
        return jsonify({"success": success_count, "failed": 0, "errors": []}), 200
    except Exception as e:
        conn.rollback()
        logging.error(f"Bulk suspend error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)

@app.route('/api/admin/bulk/activate', methods=['POST'])
def admin_bulk_activate():
    """Activate multiple user licenses"""
    api_key = request.headers.get('X-Admin-API-Key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    license_keys = data.get('license_keys', [])
    
    if not license_keys or len(license_keys) > 100:
        return jsonify({"error": "Invalid request"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE users 
            SET license_status = 'ACTIVE'
            WHERE license_key = ANY(%s)
        """, (license_keys,))
        success_count = cur.rowcount
        conn.commit()
        logging.info(f"Bulk activated {success_count} users")
        return jsonify({"success": success_count, "failed": 0, "errors": []}), 200
    except Exception as e:
        conn.rollback()
        logging.error(f"Bulk activate error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)

@app.route('/api/admin/bulk/delete', methods=['POST'])
def admin_bulk_delete():
    """Delete multiple user licenses"""
    api_key = request.headers.get('X-Admin-API-Key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    license_keys = data.get('license_keys', [])
    
    if not license_keys or len(license_keys) > 100:
        return jsonify({"error": "Invalid request"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            DELETE FROM users 
            WHERE license_key = ANY(%s)
        """, (license_keys,))
        success_count = cur.rowcount
        conn.commit()
        logging.info(f"Bulk deleted {success_count} users")
        return jsonify({"success": success_count, "failed": 0, "errors": []}), 200
    except Exception as e:
        conn.rollback()
        logging.error(f"Bulk delete error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)

# ============================================================================
# DATABASE VIEWER ENDPOINT
# ============================================================================

@app.route('/api/admin/database/<table_name>', methods=['GET'])
def admin_view_database_table(table_name):
    """View raw database table contents (admin only)"""
    api_key = request.args.get('admin_key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Whitelist allowed tables - SECURITY: Strictly validated before use
    allowed_tables = ['users', 'api_logs', 'heartbeats']
    if table_name not in allowed_tables:
        return jsonify({"error": f"Table '{table_name}' not allowed"}), 400
    
    limit = request.args.get('limit', 100, type=int)
    if limit > 1000:
        limit = 1000  # Max 1000 rows
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database unavailable"}), 503
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # SECURITY: Use psycopg2.sql.Identifier to safely include table name
        # Even though table_name is whitelisted, this is defense-in-depth
        table_identifier = psycopg2_sql.Identifier(table_name)
        
        # Get total row count - using parameterized query with Identifier
        count_query = psycopg2_sql.SQL("SELECT COUNT(*) FROM {}").format(table_identifier)
        cur.execute(count_query)
        total_rows = cur.fetchone()['count']
        
        # Fetch recent rows (ordered by most recent first)
        # Using psycopg2.sql for safe table name inclusion
        select_query = psycopg2_sql.SQL("""
            SELECT * FROM {}
            ORDER BY created_at DESC
            LIMIT %s
        """).format(table_identifier)
        cur.execute(select_query, (limit,))
        
        rows = cur.fetchall()
        
        # Convert datetime objects to ISO strings
        for row in rows:
            for key, value in row.items():
                if hasattr(value, 'isoformat'):
                    row[key] = value.isoformat()
        
        return jsonify({
            "table": table_name,
            "total_rows": total_rows,
            "rows_returned": len(rows),
            "rows": rows
        }), 200
        
    except Exception as e:
        logging.error(f"Database viewer error for {table_name}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)

@app.route('/api/admin/webhooks', methods=['GET'])
def admin_get_webhooks():
    """Get webhook event history (admin only)"""
    api_key = request.args.get('license_key') or request.args.get('admin_key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = request.args.get('limit', 100, type=int)
    if limit > 500:
        limit = 500
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"webhooks": []}), 200
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if webhook_events table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'webhook_events'
            )
        """)
        table_exists = cur.fetchone()['exists']
        
        if not table_exists:
            # Create webhook_events table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR(100),
                    whop_id VARCHAR(100),
                    user_id VARCHAR(100),
                    email VARCHAR(255),
                    status VARCHAR(50),
                    details TEXT,
                    error TEXT,
                    payload JSONB
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_webhook_events_timestamp ON webhook_events(timestamp DESC)")
            conn.commit()
            return jsonify({"webhooks": []}), 200
        
        # Fetch recent webhooks
        cur.execute("""
            SELECT * FROM webhook_events
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        
        # Convert datetime to ISO
        for row in rows:
            if row.get('timestamp'):
                row['timestamp'] = row['timestamp'].isoformat()
        
        return jsonify({"webhooks": rows}), 200
        
    except Exception as e:
        logging.error(f"Webhooks fetch error: {e}")
        return jsonify({"webhooks": []}), 200
    finally:
        cur.close()
        return_connection(conn)

@app.route('/api/admin/security-events', methods=['GET'])
def admin_get_security_events():
    """Get security event history (rate limits, suspicious activity) - admin only"""
    api_key = request.args.get('license_key') or request.args.get('admin_key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    limit = request.args.get('limit', 100, type=int)
    if limit > 500:
        limit = 500
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"events": []}), 200
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if security_events table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'security_events'
            )
        """)
        table_exists = cur.fetchone()['exists']
        
        if not table_exists:
            # Create security_events table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS security_events (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    license_key VARCHAR(255),
                    email VARCHAR(255),
                    endpoint VARCHAR(255),
                    attempts INTEGER,
                    reason TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_security_events_license ON security_events(license_key)")
            conn.commit()
            return jsonify({"events": []}), 200
        
        # Fetch recent security events
        cur.execute("""
            SELECT * FROM security_events
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        
        # Convert datetime to ISO
        for row in rows:
            if row.get('timestamp'):
                row['timestamp'] = row['timestamp'].isoformat()
        
        return jsonify({"events": rows}), 200
        
    except Exception as e:
        logging.error(f"Security events fetch error: {e}")
        return jsonify({"events": []}), 200
    finally:
        cur.close()
        return_connection(conn)

# ============================================================================
# USER RETENTION METRICS ENDPOINT
# ============================================================================

@app.route('/api/admin/metrics/retention', methods=['GET'])
def admin_retention_metrics():
    """Get comprehensive retention and engagement metrics"""
    api_key = request.headers.get('X-Admin-API-Key')
    if api_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Churn rate (last 30 days)
        cur.execute("""
            WITH expired_users AS (
                SELECT 
                    COUNT(*) as total_expired,
                    COUNT(*) FILTER (WHERE license_status = 'CANCELLED' OR license_status = 'EXPIRED') as churned
                FROM users
                WHERE license_expiration BETWEEN NOW() - INTERVAL '30 days' AND NOW()
            )
            SELECT 
                CASE WHEN total_expired > 0 
                    THEN (churned * 100.0 / total_expired)
                    ELSE 0 
                END as churn_rate
            FROM expired_users
        """)
        churn_data = cur.fetchone()
        churn_rate = float(churn_data['churn_rate']) if churn_data else 0.0
        
        # Average subscription length in months
        cur.execute("""
            SELECT 
                AVG(EXTRACT(DAY FROM license_expiration - created_at) / 30.0) as avg_months
            FROM users
            WHERE created_at IS NOT NULL
        """)
        avg_sub = cur.fetchone()
        avg_subscription_months = float(avg_sub['avg_months']) if avg_sub and avg_sub['avg_months'] else 0.0
        
        # Active usage rate (users with API calls in last 24h)
        cur.execute("""
            WITH active_licenses AS (
                SELECT COUNT(*) as total
                FROM users
                WHERE license_status = 'ACTIVE'
            ),
            recent_activity AS (
                SELECT COUNT(DISTINCT license_key) as active
                FROM api_logs
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            )
            SELECT 
                CASE WHEN al.total > 0
                    THEN (ra.active * 100.0 / al.total)
                    ELSE 0
                END as usage_rate
            FROM active_licenses al, recent_activity ra
        """)
        usage_data = cur.fetchone()
        active_usage_rate = float(usage_data['usage_rate']) if usage_data else 0.0
        
        # Renewal rate (users who renewed vs expired in last 30 days)
        cur.execute("""
            WITH expired_last_month AS (
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE license_status = 'ACTIVE') as renewed
                FROM users
                WHERE license_expiration BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days'
            )
            SELECT 
                CASE WHEN total > 0
                    THEN (renewed * 100.0 / total)
                    ELSE 0
                END as renewal_rate
            FROM expired_last_month
        """)
        renewal_data = cur.fetchone()
        renewal_rate = float(renewal_data['renewal_rate']) if renewal_data else 0.0
        
        # Lifetime value
        cur.execute("""
            SELECT 
                AVG(
                    CASE 
                        WHEN license_type = 'MONTHLY' THEN (EXTRACT(DAY FROM license_expiration - created_at) / 30.0) * 200.00
                        WHEN license_type = 'ANNUAL' THEN (EXTRACT(DAY FROM license_expiration - created_at) / 365.0) * 2000.00
                        ELSE 0
                    END
                ) as avg_ltv
            FROM users
            WHERE created_at IS NOT NULL
        """)
        ltv_data = cur.fetchone()
        lifetime_value = float(ltv_data['avg_ltv']) if ltv_data and ltv_data['avg_ltv'] else 0.0
        
        # Inactive users (no API calls in 7+ days)
        cur.execute("""
            SELECT 
                l.account_id,
                l.email,
                MAX(a.timestamp) as last_active,
                EXTRACT(DAY FROM NOW() - MAX(a.timestamp)) as days_inactive
            FROM users l
            LEFT JOIN api_logs a ON l.license_key = a.license_key
            WHERE l.license_status = 'ACTIVE'
            GROUP BY l.account_id, l.email
            HAVING MAX(a.timestamp) < NOW() - INTERVAL '7 days' OR MAX(a.timestamp) IS NULL
            ORDER BY days_inactive DESC NULLS FIRST
            LIMIT 20
        """)
        inactive_users = cur.fetchall()
        
        # Cohort retention (last 12 months)
        cur.execute("""
            SELECT 
                TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM') as cohort_month,
                COUNT(*) as total_signups,
                COUNT(*) FILTER (WHERE license_status = 'ACTIVE') as still_active,
                CASE WHEN COUNT(*) > 0
                    THEN (COUNT(*) FILTER (WHERE license_status = 'ACTIVE') * 100.0 / COUNT(*))
                    ELSE 0
                END as retention_pct
            FROM users
            WHERE created_at >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY cohort_month DESC
        """)
        cohort_retention = cur.fetchall()
        
        # Churn trend (this month vs last month)
        cur.execute("""
            SELECT 
                DATE_TRUNC('month', license_expiration) as month,
                COUNT(*) FILTER (WHERE license_status = 'CANCELLED' OR license_status = 'EXPIRED') * 100.0 / COUNT(*) as churn
            FROM users
            WHERE license_expiration >= NOW() - INTERVAL '60 days'
            GROUP BY DATE_TRUNC('month', license_expiration)
            ORDER BY month DESC
            LIMIT 2
        """)
        churn_trend_data = cur.fetchall()
        churn_trend = {
            "this_month": float(churn_trend_data[0]['churn']) if len(churn_trend_data) > 0 else churn_rate,
            "last_month": float(churn_trend_data[1]['churn']) if len(churn_trend_data) > 1 else churn_rate
        }
        
        return jsonify({
            "churn_rate": round(churn_rate, 2),
            "churn_trend": churn_trend,
            "avg_subscription_months": round(avg_subscription_months, 2),
            "active_usage_rate": round(active_usage_rate, 2),
            "renewal_rate": round(renewal_rate, 2),
            "lifetime_value": round(lifetime_value, 2),
            "inactive_users": [
                {
                    "account_id": user['account_id'][:12] + "..." if user['account_id'] else "N/A",
                    "email": user['email'],
                    "last_active": user['last_active'].isoformat() if user['last_active'] else "Never",
                    "days_inactive": int(user['days_inactive']) if user['days_inactive'] else 999
                }
                for user in inactive_users
            ],
            "cohort_retention": [
                {
                    "month": cohort['cohort_month'],
                    "signups": cohort['total_signups'],
                    "still_active": cohort['still_active'],
                    "retention": round(float(cohort['retention_pct']), 1)
                }
                for cohort in cohort_retention
            ]
        }), 200
    except Exception as e:
        logging.error(f"Retention metrics error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        return_connection(conn)


@app.route('/admin-dashboard-full.html')
def serve_admin_dashboard():
    """Serve the admin dashboard HTML file"""
    return send_from_directory('.', 'admin-dashboard-full.html')


# ============================================================================
# ZONE MANAGEMENT FOR SUPPLY/DEMAND TRADING STRATEGY
# ============================================================================

# In-memory zone storage (keyed by *canonical symbol group*)
# Structure: { "ES": [zone1, ...], "NQ": [...], ... }
# NOTE: These are shared groups:
# - ES zones are shared with MES
# - NQ zones are shared with MNQ
_zones_by_symbol = {}
_zones_last_update_utc = {}

# Retention limits (prevent unbounded growth)
ZONES_MAX_PER_SYMBOL = int(os.environ.get("ZONES_MAX_PER_SYMBOL", "250"))

# Auto-expiry (seconds). If TradingView stops sending, zones will age out.
# Set to 0 to disable TTL expiry.
ZONES_TTL_SECONDS = int(os.environ.get("ZONES_TTL_SECONDS", "900"))


def canonical_zone_symbol(symbol: str) -> str:
    """Normalize a symbol to its shared zones group key."""
    if not symbol:
        return symbol
    s = symbol.strip().upper()
    if s in ("MES",):
        return "ES"
    if s in ("MNQ",):
        return "NQ"
    return s


def _prune_stale_zones(now_utc: datetime | None = None) -> None:
    """Remove zone groups that haven't been updated within TTL."""
    if ZONES_TTL_SECONDS <= 0:
        return
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    stale_keys = []
    for key, last_dt in _zones_last_update_utc.items():
        if last_dt is None:
            continue
        age_seconds = (now_utc - last_dt).total_seconds()
        if age_seconds > ZONES_TTL_SECONDS:
            stale_keys.append(key)

    for key in stale_keys:
        removed = len(_zones_by_symbol.get(key, []))
        _zones_by_symbol.pop(key, None)
        _zones_last_update_utc.pop(key, None)
        logging.info(f"🕒 Zones TTL expired for {key} (removed {removed})")


def get_zones_for_symbol(symbol: str) -> list:
    """
    Get zones for a specific symbol.
    
    Args:
        symbol: Trading symbol (e.g., "ES", "NQ")
        
    Returns:
        List of zones for the symbol
    """
    _prune_stale_zones()
    key = canonical_zone_symbol(symbol)
    return _zones_by_symbol.get(key, [])


def set_zones_for_symbol(symbol: str, zones: list) -> None:
    """
    Set zones for a specific symbol (replaces existing zones).
    
    Args:
        symbol: Trading symbol
        zones: List of zone dictionaries
    """
    _prune_stale_zones()
    key = canonical_zone_symbol(symbol)
    zones = zones or []
    if len(zones) > ZONES_MAX_PER_SYMBOL:
        zones = zones[-ZONES_MAX_PER_SYMBOL:]
    _zones_by_symbol[key] = zones
    _zones_last_update_utc[key] = datetime.now(timezone.utc)
    logging.info(f"📍 Zones updated for {key}: {len(zones)} zones")


def add_zone_for_symbol(symbol: str, zone: dict) -> None:
    """
    Add a single zone to a symbol's zone list.
    
    Args:
        symbol: Trading symbol
        zone: Zone dictionary
    """
    _prune_stale_zones()
    key = canonical_zone_symbol(symbol)
    if key not in _zones_by_symbol:
        _zones_by_symbol[key] = []
    _zones_by_symbol[key].append(zone)
    if len(_zones_by_symbol[key]) > ZONES_MAX_PER_SYMBOL:
        _zones_by_symbol[key] = _zones_by_symbol[key][-ZONES_MAX_PER_SYMBOL:]
    _zones_last_update_utc[key] = datetime.now(timezone.utc)
    try:
        logging.info(f"📍 Zone added to {key}: {zone.get('zone_type')} {zone.get('zone_bottom')}-{zone.get('zone_top')}")
    except Exception:
        logging.info(f"📍 Zone added to {key}")


def _require_admin_key_from_request() -> bool:
    admin_key = request.args.get('admin_key', '')
    return bool(admin_key) and admin_key == ADMIN_API_KEY


@app.route('/api/admin/zones/symbols', methods=['GET'])
def admin_list_zone_symbols():
    """List canonical symbols that currently have zone data."""
    if not _require_admin_key_from_request():
        return jsonify({"error": "Unauthorized"}), 401
    _prune_stale_zones()
    symbols = sorted(_zones_by_symbol.keys())
    last_update = {k: format_datetime_utc(_zones_last_update_utc.get(k)) for k in symbols}
    return jsonify({"symbols": symbols, "count": len(symbols), "last_update": last_update}), 200


@app.route('/api/admin/zones/latest', methods=['GET'])
def admin_get_latest_zones():
    """Fetch latest zones for a symbol group (ES/NQ/etc)."""
    if not _require_admin_key_from_request():
        return jsonify({"error": "Unauthorized"}), 401
    _prune_stale_zones()
    symbol = request.args.get('symbol', '')
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    key = canonical_zone_symbol(symbol)
    zones = get_zones_for_symbol(key)
    if key == "ES":
        shared_with = ["MES"]
    elif key == "NQ":
        shared_with = ["MNQ"]
    else:
        shared_with = []
    return jsonify({
        "symbol": key,
        "shared_with": shared_with,
        "count": len(zones),
        "last_update": format_datetime_utc(_zones_last_update_utc.get(key)),
        "zones": zones
    }), 200


@app.route('/api/admin/zones/all', methods=['GET'])
def admin_get_all_zones():
    """Fetch all current zone groups (canonical keys)."""
    if not _require_admin_key_from_request():
        return jsonify({"error": "Unauthorized"}), 401

    _prune_stale_zones()
    out = {}
    for key in sorted(_zones_by_symbol.keys()):
        if key == "ES":
            shared_with = ["MES"]
        elif key == "NQ":
            shared_with = ["MNQ"]
        else:
            shared_with = []

        out[key] = {
            "symbol": key,
            "shared_with": shared_with,
            "count": len(_zones_by_symbol.get(key, [])),
            "last_update": format_datetime_utc(_zones_last_update_utc.get(key)),
            "zones": _zones_by_symbol.get(key, [])
        }

    return jsonify({
        "ttl_seconds": ZONES_TTL_SECONDS,
        "symbols": list(out.keys()),
        "data": out
    }), 200


@app.route('/api/admin/zones/clear', methods=['POST'])
def admin_clear_zones():
    """Clear zones for a symbol group (canonical). Body: {"symbol": "ES"} or query ?symbol=ES"""
    if not _require_admin_key_from_request():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    symbol = (payload.get('symbol') or request.args.get('symbol') or '').strip()
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    key = canonical_zone_symbol(symbol)
    removed_count = len(_zones_by_symbol.get(key, []))
    _zones_by_symbol.pop(key, None)
    _zones_last_update_utc.pop(key, None)

    logging.info(f"🧹 Admin cleared zones for {key} (removed {removed_count})")
    return jsonify({"status": "success", "symbol": key, "removed": removed_count}), 200


@app.route('/api/admin/zones/clear-all', methods=['POST'])
def admin_clear_all_zones():
    """Clear zones for all symbols."""
    if not _require_admin_key_from_request():
        return jsonify({"error": "Unauthorized"}), 401

    total_symbols = len(_zones_by_symbol)
    total_zones = sum(len(v) for v in _zones_by_symbol.values())
    _zones_by_symbol.clear()
    _zones_last_update_utc.clear()

    logging.info(f"🧹 Admin cleared ALL zones ({total_symbols} symbols, {total_zones} zones)")
    return jsonify({"status": "success", "symbols_cleared": total_symbols, "zones_cleared": total_zones}), 200


@app.route('/api/zones/webhook', methods=['POST'])
def receive_tradingview_webhook():
    """
    Receive zone data from TradingView via webhooks.
    
    Expected JSON payload:
    {
        "action": "new" or "sync",
        "symbol": "ES",
        "timeframe": "5m",
        "zones": [
            {
                "zone_type": "supply" or "demand",
                "zone_top": 4500.00,
                "zone_bottom": 4495.00,
                "zone_strength": "strong" or "medium" or "weak"
            },
            ...
        ]
    }
    
    Actions:
    - "new": Add zones to existing list
    - "sync": Replace entire zone list with new zones
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
        
        action = data.get('action', 'sync')
        symbol = data.get('symbol')
        zones = data.get('zones', [])
        timeframe = data.get('timeframe', 'unknown')
        
        if not symbol:
            return jsonify({"status": "error", "message": "Symbol is required"}), 400
        
        if action not in ['new', 'sync']:
            return jsonify({"status": "error", "message": "Action must be 'new' or 'sync'"}), 400
        
        # Validate zones
        for zone in zones:
            required_fields = ['zone_type', 'zone_top', 'zone_bottom', 'zone_strength']
            for field in required_fields:
                if field not in zone:
                    return jsonify({
                        "status": "error",
                        "message": f"Zone missing required field: {field}"
                    }), 400
            
            # Validate zone_type
            if zone['zone_type'] not in ['supply', 'demand']:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid zone_type: {zone['zone_type']} (must be 'supply' or 'demand')"
                }), 400
            
            # Validate zone_strength
            if zone['zone_strength'] not in ['strong', 'medium', 'weak']:
                return jsonify({
                    "status": "error",
                    "message": f"Invalid zone_strength: {zone['zone_strength']}"
                }), 400
        
        # Process action (store under canonical shared symbol)
        if action == 'sync':
            # Replace entire zone list
            set_zones_for_symbol(symbol, zones)
            logging.info(f"📍 TradingView webhook: SYNC {len(zones)} zones for {canonical_zone_symbol(symbol)} ({timeframe})")
        else:  # action == 'new'
            # Add zones to existing list
            for zone in zones:
                add_zone_for_symbol(symbol, zone)
            logging.info(f"📍 TradingView webhook: NEW {len(zones)} zones for {canonical_zone_symbol(symbol)} ({timeframe})")
        
        return jsonify({
            "status": "success",
            "message": f"{len(zones)} zones processed",
            "action": action,
            "symbol": canonical_zone_symbol(symbol),
            "timeframe": timeframe,
            "total_zones": len(get_zones_for_symbol(symbol))
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Webhook error: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e)}), 500


# Global error handlers for production safety
@app.errorhandler(413)
def request_too_large(error):
    """Handle requests that exceed size limit"""
    logging.warning(f"Request too large from {request.remote_addr}")
    return jsonify({"error": "Request size exceeds 10MB limit"}), 413


@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit errors"""
    return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors gracefully"""
    logging.error(f"Internal server error: {error}")
    logging.error(traceback.format_exc())
    return jsonify({
        "error": "Internal server error. Please try again later.",
        "support": "Contact support if this persists"
    }), 500


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Catch-all error handler to prevent crashes"""
    logging.error(f"Unexpected error: {type(error).__name__}: {str(error)}")
    logging.error(traceback.format_exc())
    
    # Don't expose internal details to clients
    return jsonify({
        "error": "An unexpected error occurred",
        "type": type(error).__name__
    }), 500


if __name__ == '__main__':
    init_database_if_needed()
    port = int(os.environ.get('PORT', 5000))
    # Use socketio.run for WebSocket support
    socketio.run(app, host='0.0.0.0', port=port, debug=False)


# =============================================================================
# WEBSOCKET HANDLERS - Real-time Zone Delivery
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Client connected to WebSocket"""
    websocket_stats['connected_clients'][request.sid] = {
        'connected_at': datetime.now(timezone.utc).isoformat(),
        'symbols': []
    }
    websocket_stats['total_connections'] += 1
    logging.info(f"🔌 WebSocket client connected: {request.sid}")
    emit('connected', {'message': 'Connected to QuoTrading Zone Server', 'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected from WebSocket"""
    if request.sid in websocket_stats['connected_clients']:
        del websocket_stats['connected_clients'][request.sid]
    logging.info(f"🔌 WebSocket client disconnected: {request.sid}")


@socketio.on('subscribe')
def handle_subscribe(data):
    """
    Client subscribes to zones for specific symbols.
    
    data: {
        "symbols": ["ES", "NQ"],  # or ["MES"] which maps to ES room
        "license_key": "optional for validation"
    }
    """
    symbols = data.get('symbols', [])
    if isinstance(symbols, str):
        symbols = [symbols]
    
    rooms_joined = []
    for symbol in symbols:
        base_symbol = get_base_symbol(symbol)
        join_room(base_symbol)
        rooms_joined.append(base_symbol)
        logging.info(f"📥 Client {request.sid} subscribed to {base_symbol} (from {symbol})")
    
    # Send current active zones for subscribed symbols
    all_zones = {}
    for base_symbol in set(rooms_joined):
        zones = get_zones_for_symbol(base_symbol)
        all_zones[base_symbol] = zones
    
    emit('subscribed', {
        'message': f'Subscribed to zones for: {", ".join(set(rooms_joined))}',
        'rooms': list(set(rooms_joined)),
        'current_zones': all_zones
    })


@socketio.on('unsubscribe')
def handle_unsubscribe(data):
    """Client unsubscribes from zone updates for specific symbols."""
    symbols = data.get('symbols', [])
    if isinstance(symbols, str):
        symbols = [symbols]
    
    for symbol in symbols:
        base_symbol = get_base_symbol(symbol)
        leave_room(base_symbol)
        logging.info(f"📤 Client {request.sid} unsubscribed from {base_symbol}")
    
    emit('unsubscribed', {'message': f'Unsubscribed from: {", ".join(symbols)}'})


@socketio.on('ping')
def handle_ping():
    """Keep-alive ping from client"""
    emit('pong', {'timestamp': datetime.now(timezone.utc).isoformat()})


# ============================================
# TRADE COPIER API ENDPOINTS
# ============================================

# In-memory storage for connected followers
_connected_followers = {}  # follower_key -> {name, account_ids, connected_at, last_heartbeat, copy_enabled, ...}
_pending_signals = {}      # follower_key -> [list of pending signals]
_copier_websocket_clients = {}  # sid -> {license_key, connected_at}


@app.route('/copier/register', methods=['POST'])
def copier_register():
    """Follower registers with the relay server."""
    data = request.get_json()
    follower_key = data.get('follower_key')
    follower_name = data.get('follower_name', 'Unknown')
    account_ids = data.get('account_ids', [])
    device_fingerprint = data.get('device_fingerprint', '')
    
    if not follower_key:
        return jsonify({"error": "Missing follower_key"}), 400
    
    # Check for duplicate session - same license already running on different device
    if follower_key in _connected_followers:
        existing = _connected_followers[follower_key]
        existing_device = existing.get('device_fingerprint', '')
        last_heartbeat_str = existing.get('last_heartbeat', '')
        
        # Check if session is still active (heartbeat within last 60 seconds)
        if last_heartbeat_str:
            try:
                last_hb = datetime.fromisoformat(last_heartbeat_str.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                time_since = (now - last_hb).total_seconds()
                
                # If active and different device, block
                if time_since < 60 and existing_device and existing_device != device_fingerprint:
                    logging.warning(f"🚫 Duplicate copier session blocked: {follower_key[:8]}... already active on another device")
                    return jsonify({
                        "error": "License already in use on another device",
                        "message": "This license is currently active on another device. Please close that session first."
                    }), 409
            except:
                pass
    
    now = datetime.now(timezone.utc).isoformat()
    
    _connected_followers[follower_key] = {
        'name': follower_name,
        'account_ids': account_ids,
        'device_fingerprint': device_fingerprint,
        'connected_at': now,
        'last_heartbeat': now,
        'copy_enabled': True,
        'signals_received': 0,
        'signals_executed': 0
    }
    
    if follower_key not in _pending_signals:
        _pending_signals[follower_key] = []
    
    logging.info(f"✅ Copier follower registered: {follower_name} ({follower_key[:8]}...) - {len(account_ids)} accounts")
    
    return jsonify({"status": "registered", "follower_key": follower_key})


@app.route('/copier/heartbeat', methods=['POST'])
def copier_heartbeat():
    """Follower sends heartbeat to stay connected."""
    data = request.get_json()
    follower_key = data.get('follower_key')
    
    if follower_key in _connected_followers:
        _connected_followers[follower_key]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        
        # Store extra metadata if provided
        if 'metadata' in data:
            _connected_followers[follower_key]['metadata'] = data['metadata']
            
        # Store position data if provided
        if 'current_position' in data:
            _connected_followers[follower_key]['current_position'] = data['current_position']
            
        return jsonify({"status": "ok"})
    
    return jsonify({"error": "Not registered"}), 401


@app.route('/copier/unregister', methods=['POST'])
def copier_unregister():
    """Follower disconnects from relay server."""
    data = request.get_json()
    follower_key = data.get('follower_key')
    
    if follower_key in _connected_followers:
        name = _connected_followers[follower_key].get('name', 'Unknown')
        del _connected_followers[follower_key]
        if follower_key in _pending_signals:
            del _pending_signals[follower_key]
        logging.info(f"🔌 Copier follower unregistered: {name}")
    
    return jsonify({"status": "unregistered"})


@app.route('/copier/broadcast', methods=['POST'])
def copier_broadcast():
    """Master broadcasts a signal to all connected followers."""
    data = request.get_json()
    master_key = data.get('master_key')
    signal = data.get('signal')
    
    if not master_key or not signal:
        return jsonify({"error": "Missing master_key or signal"}), 400
    
    # Add signal to all connected followers' queues (for HTTP polling fallback)
    received_count = 0
    for follower_key, follower in _connected_followers.items():
        if follower.get('copy_enabled', True):
            if follower_key not in _pending_signals:
                _pending_signals[follower_key] = []
            _pending_signals[follower_key].append(signal)
            received_count += 1
    
    # ALSO broadcast via WebSocket for instant delivery
    websocket_count = len(_copier_websocket_clients)
    if websocket_count > 0:
        socketio.emit('trade_signal', signal, namespace='/copier')
        logging.info(f"📡 WebSocket push to {websocket_count} clients")
    
    logging.info(f"📤 Copier signal broadcast: {signal.get('action')} {signal.get('side')} {signal.get('quantity')} {signal.get('symbol')} → {received_count} HTTP + {websocket_count} WS")
    
    return jsonify({"received_count": received_count, "websocket_count": websocket_count})


@app.route('/copier/poll', methods=['GET'])
def copier_poll():
    """Follower polls for new signals."""
    follower_key = request.args.get('follower_key')
    
    if not follower_key or follower_key not in _connected_followers:
        return jsonify({"error": "Not registered"}), 401
    
    # Update heartbeat
    _connected_followers[follower_key]['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
    
    # Check for pending signals
    if follower_key in _pending_signals and _pending_signals[follower_key]:
        signal = _pending_signals[follower_key].pop(0)
        _connected_followers[follower_key]['signals_received'] = \
            _connected_followers[follower_key].get('signals_received', 0) + 1
        return jsonify({"signal": signal})
    
    # No signals
    return '', 204


@app.route('/copier/report', methods=['POST'])
def copier_report():
    """Follower reports successful signal execution."""
    data = request.get_json()
    follower_key = data.get('follower_key')
    status = data.get('status')
    
    if follower_key in _connected_followers:
        if status == 'executed':
            _connected_followers[follower_key]['signals_executed'] = \
                _connected_followers[follower_key].get('signals_executed', 0) + 1
        
        # Store extra metadata if provided
        if 'metadata' in data:
            _connected_followers[follower_key]['metadata'] = data['metadata']
        
        # Store position data if provided
        current_position = data.get('current_position')
        if current_position:
            _connected_followers[follower_key]['current_position'] = current_position
        
        return jsonify({"status": "ok"})
    
    return jsonify({"status": "reported"})


@app.route('/copier/followers', methods=['GET'])
def copier_followers():
    """Get list of connected followers (for master dashboard)."""
    followers = []
    for follower_key, follower in _connected_followers.items():
        followers.append({
            'client_id': follower_key,
            'name': follower['name'],
            'account_ids': follower.get('account_ids', []),
            'connected_at': follower['connected_at'],
            'last_heartbeat': follower['last_heartbeat'],
            'copy_enabled': follower.get('copy_enabled', True),
            'signals_received': follower.get('signals_received', 0),
            'signals_executed': follower.get('signals_executed', 0),
            'current_position': follower.get('current_position')
        })
    
    return jsonify({"followers": followers})


@app.route('/copier/toggle_follower', methods=['POST'])
def copier_toggle_follower():
    """Toggle copy on/off for a specific follower."""
    data = request.get_json()
    follower_key = data.get('follower_key')
    
    if follower_key in _connected_followers:
        _connected_followers[follower_key]['copy_enabled'] = \
            not _connected_followers[follower_key].get('copy_enabled', True)
        return jsonify({
            "follower_key": follower_key,
            "copy_enabled": _connected_followers[follower_key]['copy_enabled']
        })
    
    return jsonify({"error": "Follower not found"}), 404


@app.route('/copier/status', methods=['GET'])
def copier_status():
    """Get overall copier system status."""
    return jsonify({
        "active_followers": len(_connected_followers),
        "total_pending_signals": sum(len(s) for s in _pending_signals.values()),
        "server_time": datetime.now(timezone.utc).isoformat()
    })


@app.route('/copier/validate-license', methods=['POST'])
def copier_validate_license():
    """Validate license and return expiration for copier clients."""
    data = request.get_json()
    license_key = data.get('license_key', '')
    
    if not license_key:
        return jsonify({"valid": False, "error": "Missing license_key"}), 400
    
    is_valid, message, expiration = validate_license(license_key)
    
    # Format expiration as ISO string
    expiration_str = None
    if expiration:
        if hasattr(expiration, 'isoformat'):
            expiration_str = expiration.isoformat()
        else:
            expiration_str = str(expiration)
    
    return jsonify({
        "valid": is_valid,
        "message": message,
        "expiration_date": expiration_str
    })


@app.route('/api/admin/copier-users', methods=['GET'])
def admin_copier_users():
    """Get enhanced follower data with user license info for admin dashboard."""
    admin_key = request.args.get('license_key') or request.args.get('admin_key')
    if admin_key != ADMIN_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    if not conn:
        # Return basic follower data without DB enrichment
        followers = []
        for follower_key, follower in _connected_followers.items():
            followers.append({
                'license_key': follower_key,
                'email': 'unknown@email.com',
                'license_status': 'UNKNOWN',
                'license_type': 'UNKNOWN',
                'license_expiration': None,
                'is_online': True,  # If in _connected_followers, they're online
                'name': follower.get('name', 'Unknown'),
                'connected_at': follower.get('connected_at'),
                'last_heartbeat': follower.get('last_heartbeat'),
                'copy_enabled': follower.get('copy_enabled', True),
                'signals_received': follower.get('signals_received', 0),
                'signals_executed': follower.get('signals_executed', 0),
                'current_position': follower.get('current_position'),
                'session_pnl': follower.get('metadata', {}).get('session_pnl', 0),
                'trades_today': follower.get('metadata', {}).get('trades_executed', 0)
            })
        return jsonify({"users": followers})
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get all users with active licenses
            cursor.execute("""
                SELECT 
                    license_key, email, license_type, license_status, 
                    license_expiration, created_at, account_id,
                    last_active, trade_count
                FROM users
                ORDER BY created_at DESC
            """)
            users = cursor.fetchall()
            
            # Enhance with follower copier data
            users_list = []
            now_utc = datetime.now(timezone.utc)
            
            for user in users:
                license_key = user['license_key']
                
                # Check if this user is connected as a follower
                follower = _connected_followers.get(license_key)
                
                if follower:
                    # User is online - check heartbeat freshness
                    last_hb_str = follower.get('last_heartbeat', '')
                    is_online = False
                    if last_hb_str:
                        try:
                            last_hb = datetime.fromisoformat(last_hb_str.replace('Z', '+00:00'))
                            time_since = (now_utc - last_hb).total_seconds()
                            is_online = time_since < 60  # Online if heartbeat within last 60 seconds
                        except:
                            pass
                    
                    # Get position and PNL data
                    current_position = follower.get('current_position')
                    metadata = follower.get('metadata', {})
                    session_pnl = metadata.get('session_pnl', 0)
                    trades_executed = metadata.get('trades_executed', 0)
                    
                    # Extract symbol and position from current_position
                    symbol = current_position.get('symbol', '-') if current_position else '-'
                    position_str = '-'
                    if current_position and current_position.get('qty', 0) > 0:
                        side = current_position.get('side', '')
                        qty = current_position.get('qty', 0)
                        position_str = f"{side} {qty}"
                    
                    users_list.append({
                        'account_id': user['account_id'],
                        'license_key': license_key,
                        'email': user['email'],
                        'license_status': user['license_status'],
                        'license_type': user['license_type'],
                        'license_expiration': format_datetime_utc(user['license_expiration']),
                        'created_at': format_datetime_utc(user['created_at']),
                        'is_online': is_online,
                        'last_active': follower.get('last_heartbeat') if is_online else format_datetime_utc(user.get('last_active')),
                        'trade_count': user.get('trade_count', 0),
                        # Copier-specific data
                        'bot_status': {
                            'symbol': symbol,
                            'session_pnl': session_pnl,
                            'trades_today': trades_executed,
                            'win_rate': None,  # Not tracked yet
                            'position': position_str
                        },
                        'copy_enabled': follower.get('copy_enabled', True),
                        'signals_received': follower.get('signals_received', 0),
                        'signals_executed': follower.get('signals_executed', 0),
                        'connected_at': follower.get('connected_at')
                    })
                else:
                    # User is offline
                    users_list.append({
                        'account_id': user['account_id'],
                        'license_key': license_key,
                        'email': user['email'],
                        'license_status': user['license_status'],
                        'license_type': user['license_type'],
                        'license_expiration': format_datetime_utc(user['license_expiration']),
                        'created_at': format_datetime_utc(user['created_at']),
                        'is_online': False,
                        'last_active': format_datetime_utc(user.get('last_active')),
                        'trade_count': user.get('trade_count', 0),
                        'bot_status': None,
                        'copy_enabled': False,
                        'signals_received': 0,
                        'signals_executed': 0,
                        'connected_at': None
                    })
            
            return jsonify({"users": users_list})
            
    except Exception as e:
        logging.error(f"Admin copier users error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        return_connection(conn)


# ============================================
# COPIER WEBSOCKET HANDLERS
# Real-time signal push for instant trade execution
# ============================================

@socketio.on('connect', namespace='/copier')
def copier_ws_connect():
    """Handle copier WebSocket connection."""
    sid = request.sid
    _copier_websocket_clients[sid] = {
        'connected_at': datetime.now(timezone.utc).isoformat(),
        'license_key': None
    }
    logging.info(f"📡 Copier WS client connected: {sid} (Total: {len(_copier_websocket_clients)})")
    emit('connected', {'status': 'ok', 'sid': sid})


@socketio.on('disconnect', namespace='/copier')
def copier_ws_disconnect():
    """Handle copier WebSocket disconnection."""
    sid = request.sid
    if sid in _copier_websocket_clients:
        del _copier_websocket_clients[sid]
    logging.info(f"📡 Copier WS client disconnected: {sid} (Remaining: {len(_copier_websocket_clients)})")


@socketio.on('subscribe', namespace='/copier')
def copier_ws_subscribe(data):
    """Follower subscribes to receive signals with their license key."""
    sid = request.sid
    license_key = data.get('license_key', '')
    
    if sid in _copier_websocket_clients:
        _copier_websocket_clients[sid]['license_key'] = license_key
    
    logging.info(f"📡 Copier WS client subscribed: {sid}")
    emit('subscribed', {'status': 'ok', 'message': 'Ready to receive trade signals'})


@socketio.on('ping', namespace='/copier')
def copier_ws_ping():
    """Keep-alive ping from copier client."""
    emit('pong', {'timestamp': datetime.now(timezone.utc).isoformat()})
