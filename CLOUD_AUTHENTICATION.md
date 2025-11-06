# QuoTrading Cloud Authentication System

This document describes the cloud-based authentication system for QuoTrading AI launcher.

## Architecture Overview

The system consists of three main components:

1. **GUI Client** (`customer/QuoTrading_Launcher.py`) - Desktop application with login screen
2. **Cloud Validation Server** (`validation_server.py`) - Flask API for credential validation
3. **Configuration** - Secure credential storage

## Part 1: GUI Client (Customer-Facing)

### Login Screen Features

The first screen now displays a **Login** interface with:

- **Username field** - User's account username
- **Password field** - User's account password (masked)
- **API Key field** - User's QuoTrading API key (masked)
- **LOGIN button** - Validates credentials with cloud server
- **Loading spinner** - Shows during validation
- **Error handling** - Displays clear error messages

### User Flow

1. User enters username, password, and API key
2. Clicks "LOGIN" button
3. Application shows loading spinner
4. Credentials sent to cloud server via HTTPS
5. Server validates and responds
6. On success: User proceeds to next screen
7. On failure: Error message displayed

### GUI Changes from Previous Version

**Before:**
- "Create Your Account" screen
- Username and password fields only
- "Remember credentials" checkbox
- Local validation only

**After:**
- "QuoTrading Login" screen
- Username, password, AND API key fields
- Cloud-based validation
- No local credential storage until validated
- Enhanced security with server-side verification

## Part 2: Cloud Validation Server

### Server Setup

The Flask server (`validation_server.py`) provides:

- **Endpoint**: `POST /api/validate`
- **Authentication**: Username + Password + API Key
- **Response**: JSON with validation result
- **Logging**: All login attempts logged with timestamps
- **Security**: Password hashing, rate limiting ready

### Installation

```bash
# Install dependencies
pip install -r requirements-server.txt

# Run the server
python validation_server.py
```

The server will start on `http://0.0.0.0:5000`

### API Endpoints

#### 1. Validate Credentials
```
POST /api/validate
Content-Type: application/json

Request:
{
    "username": "demo_user",
    "password": "demo_password",
    "api_key": "DEMO_API_KEY_12345"
}

Response (Success):
{
    "valid": true,
    "message": "Credentials validated successfully",
    "user_data": {
        "email": "demo@quotrading.com",
        "account_type": "premium",
        "active": true
    }
}

Response (Failure):
{
    "valid": false,
    "message": "Invalid username or password"
}
```

#### 2. Health Check
```
GET /api/health

Response:
{
    "status": "healthy",
    "timestamp": "2025-11-06T08:00:00.000000"
}
```

### User Database

The server includes a demo user database. In production, replace with a real database:

```python
USER_DATABASE = {
    "demo_user": {
        "password": "<hashed_password>",
        "api_key": "DEMO_API_KEY_12345",
        "user_data": {
            "email": "demo@quotrading.com",
            "account_type": "premium",
            "active": True
        }
    }
}
```

**Test Accounts:**
- Username: `demo_user`, Password: `demo_password`, API Key: `DEMO_API_KEY_12345`
- Username: `test_trader`, Password: `test123`, API Key: `TEST_API_KEY_67890`

### Security Features

1. **Password Hashing**: SHA-256 hashing (upgrade to bcrypt for production)
2. **CORS Protection**: Configured for cross-origin requests
3. **Input Validation**: All fields required and validated
4. **Logging**: Complete audit trail of login attempts
5. **Error Messages**: Generic messages to prevent user enumeration

### Server Logs

The server logs all authentication attempts:

```
2025-11-06 08:00:00 - INFO - Validation attempt for user: demo_user
2025-11-06 08:00:00 - INFO - Successful validation for user: demo_user
2025-11-06 08:00:05 - WARNING - Invalid password for user: test_user
```

## Part 3: Integration

### Connecting GUI to Cloud Server

The GUI client is configured to connect to the validation server:

```python
# In QuoTrading_Launcher.py
self.VALIDATION_API_URL = "http://localhost:5000/api/validate"
```

**For Production:**
1. Deploy Flask server to cloud (AWS, Azure, Google Cloud, Heroku, etc.)
2. Update `VALIDATION_API_URL` with your cloud server URL
3. Enable HTTPS for secure transmission
4. Configure environment variables for sensitive data

### Testing the Integration

1. **Start the server:**
   ```bash
   python validation_server.py
   ```

2. **Run the GUI:**
   ```bash
   python customer/QuoTrading_Launcher.py
   ```

3. **Test login:**
   - Username: `demo_user`
   - Password: `demo_password`
   - API Key: `DEMO_API_KEY_12345`
   - Click "LOGIN"

4. **Verify:**
   - Loading spinner appears
   - Server logs show validation attempt
   - Success message displays
   - User proceeds to next screen

### Error Handling

The system handles various error scenarios:

| Error Scenario | User Message |
|----------------|--------------|
| Empty fields | "Please enter your [field name]" |
| Invalid credentials | "Authentication failed: Invalid username or password" |
| Server unavailable | "Cannot connect to validation server" |
| Request timeout | "Request timed out. Please try again" |
| Server error | "Server error: [status code]" |

## Configuration Files

### config.json (Client)

After successful login, credentials are stored locally:

```json
{
    "username": "demo_user",
    "password": "demo_password",
    "user_api_key": "DEMO_API_KEY_12345",
    "validated": true,
    "user_data": {
        "email": "demo@quotrading.com",
        "account_type": "premium",
        "active": true
    }
}
```

**Security Note:** This file contains sensitive data. Ensure it's in `.gitignore`.

## Deployment Guide

### Local Development
```bash
# Terminal 1: Start validation server
python validation_server.py

# Terminal 2: Run GUI client
python customer/QuoTrading_Launcher.py
```

### Production Deployment

#### Option 1: Heroku
```bash
# Create Procfile
echo "web: gunicorn validation_server:app" > Procfile

# Deploy
heroku create quotrading-validation
git push heroku main
```

#### Option 2: AWS Lambda + API Gateway
Use AWS SAM or Serverless Framework to deploy Flask as Lambda function.

#### Option 3: Docker Container
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements-server.txt .
RUN pip install -r requirements-server.txt
COPY validation_server.py .
CMD ["python", "validation_server.py"]
```

### Update GUI for Production

After deploying server, update the URL:

```python
# In QuoTrading_Launcher.py
self.VALIDATION_API_URL = "https://your-server.com/api/validate"
```

## Security Best Practices

1. **Use HTTPS**: Always use SSL/TLS in production
2. **Environment Variables**: Store sensitive config in env vars
3. **Rate Limiting**: Add rate limiting to prevent brute force
4. **Strong Password Hashing**: Upgrade to bcrypt or Argon2
5. **Database Encryption**: Encrypt sensitive data at rest
6. **API Key Rotation**: Implement key rotation policies
7. **Audit Logging**: Keep detailed logs of all access
8. **Input Sanitization**: Validate and sanitize all inputs
9. **Session Management**: Implement proper session handling
10. **2FA**: Consider adding two-factor authentication

## Troubleshooting

### Common Issues

**1. Cannot connect to server**
- Ensure server is running: `python validation_server.py`
- Check firewall settings
- Verify URL in GUI matches server address

**2. Login fails with valid credentials**
- Check server logs for error details
- Verify credentials in USER_DATABASE
- Ensure API key matches exactly (case-sensitive)

**3. Loading spinner doesn't disappear**
- Check network connectivity
- Look for timeout errors in console
- Verify server is responding to health check

**4. Server crashes on startup**
- Install dependencies: `pip install -r requirements-server.txt`
- Check port 5000 is not already in use
- Review server logs for errors

## Monitoring and Maintenance

### Server Monitoring

Monitor these metrics:
- Request rate (requests/minute)
- Response time (average, p95, p99)
- Error rate (4xx, 5xx)
- Active users
- Failed login attempts

### Log Analysis

Review logs regularly for:
- Unusual login patterns
- Failed authentication attempts
- Performance issues
- Error trends

### Database Maintenance

For production:
1. Regular backups
2. User cleanup (inactive accounts)
3. API key rotation
4. Password policy enforcement

## Future Enhancements

Potential improvements:
1. Multi-factor authentication (MFA)
2. OAuth2/OpenID Connect integration
3. Password reset functionality
4. Email verification
5. Account lockout after failed attempts
6. Session token management
7. WebSocket for real-time updates
8. Admin dashboard for user management
9. Analytics and usage reporting
10. Compliance logging (GDPR, SOC2)

## Support

For issues or questions:
- Check logs: Server console and `config.json`
- Review error messages in GUI
- Test with demo credentials first
- Verify network connectivity
- Contact support@quotrading.com
