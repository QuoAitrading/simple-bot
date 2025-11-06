# Quick Start Guide - Cloud Authentication

This guide will help you quickly set up and test the cloud authentication system.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Step 1: Install Dependencies

```bash
# Install server dependencies
pip install -r requirements-server.txt

# The GUI already has requests in the main requirements
```

## Step 2: Start the Validation Server

Open a terminal and run:

```bash
python validation_server.py
```

You should see:
```
Starting QuoTrading Cloud Validation Server...
Available test users:
  - demo_user
  - test_trader
 * Running on http://0.0.0.0:5000
```

**Keep this terminal open!** The server needs to be running for authentication to work.

## Step 3: Run the GUI Application

Open a **new terminal** (don't close the server terminal) and run:

```bash
python customer/QuoTrading_Launcher.py
```

## Step 4: Test Login

The login screen will appear with three fields:

1. **Username**: Enter `demo_user`
2. **Password**: Enter `demo_password`
3. **API Key**: Enter `DEMO_API_KEY_12345`
4. Click the **LOGIN** button

### What Should Happen:

1. Loading spinner appears
2. GUI sends credentials to server
3. Server validates (check server terminal for logs)
4. Success message appears: "Welcome, demo_user!"
5. You proceed to the next screen

### Server Output:
```
2025-11-06 08:00:00 - INFO - Validation attempt for user: demo_user
2025-11-06 08:00:00 - INFO - Successful validation for user: demo_user
```

## Test Accounts

### Account 1 (Premium)
- **Username**: `demo_user`
- **Password**: `demo_password`
- **API Key**: `DEMO_API_KEY_12345`

### Account 2 (Basic)
- **Username**: `test_trader`
- **Password**: `test123`
- **API Key**: `TEST_API_KEY_67890`

## Testing Error Scenarios

### Test Invalid Password
1. Username: `demo_user`
2. Password: `wrong_password`
3. API Key: `DEMO_API_KEY_12345`
4. Result: "Authentication failed: Invalid username or password"

### Test Invalid API Key
1. Username: `demo_user`
2. Password: `demo_password`
3. API Key: `WRONG_KEY`
4. Result: "Authentication failed: Invalid API key"

### Test Missing Fields
1. Leave any field empty
2. Result: Error message about required field

### Test Server Offline
1. Stop the server (Ctrl+C in server terminal)
2. Try to login
3. Result: "Cannot connect to validation server"

## Adding Your Own Users

Edit `validation_server.py` and add to the `USER_DATABASE`:

```python
USER_DATABASE = {
    # Existing users...
    
    "your_username": {
        "password": hashlib.sha256("your_password".encode()).hexdigest(),
        "api_key": "YOUR_API_KEY_HERE",
        "user_data": {
            "email": "your@email.com",
            "account_type": "premium",
            "active": True
        }
    }
}
```

**Important:** Restart the server after making changes!

## Production Deployment

When you're ready to deploy to production:

1. **Deploy the server** to a cloud provider (AWS, Azure, Heroku, etc.)
2. **Get the server URL** (e.g., `https://your-server.com`)
3. **Update the GUI** in `customer/QuoTrading_Launcher.py`:
   ```python
   self.VALIDATION_API_URL = "https://your-server.com/api/validate"
   ```
4. **Enable HTTPS** for secure communication
5. **Update USER_DATABASE** with real user credentials
6. **Set debug=False** in server for production

## Troubleshooting

**Problem:** GUI says "Cannot connect to validation server"
- **Solution**: Make sure the server is running in another terminal

**Problem:** Server says "Address already in use"
- **Solution**: Port 5000 is in use. Kill the process or change port in code

**Problem:** Login works but credentials not saved
- **Solution**: Check permissions on `config.json` file

**Problem:** Server crashes immediately
- **Solution**: Install dependencies: `pip install -r requirements-server.txt`

## Next Steps

1. Review `CLOUD_AUTHENTICATION.md` for full documentation
2. Customize the login screen styling if needed
3. Add more users to the database
4. Deploy to production when ready
5. Implement additional security features

## Support

- Server logs: Check terminal where server is running
- Client logs: Check `config.json` for saved data
- Test accounts: Use demo_user or test_trader
- Documentation: See `CLOUD_AUTHENTICATION.md`
