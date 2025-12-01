"""
Quick script to check license details in the database
"""
import os
import psycopg2
from datetime import datetime

# Use the same database config as the Flask app
DB_HOST = os.environ.get("DB_HOST", "quotrading-db.postgres.database.azure.com")
DB_NAME = os.environ.get("DB_NAME", "quotrading")
DB_USER = os.environ.get("DB_USER", "quotrading_admin")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

if not DB_PASSWORD:
    print("❌ DB_PASSWORD environment variable not set")
    print("\nTo check the license, you need to set the database password:")
    print("Run: $env:DB_PASSWORD='your-db-password'")
    print("\nOr check Azure App Service Configuration for the password")
    exit(1)

try:
    # Connect to database using the same method as Flask app
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode='require',
        connect_timeout=10
    )
    cursor = conn.cursor()
    
    # Query the license
    license_key = 'C63W-L241-FVJ9-LGIR'
    
    query = """
    SELECT 
        license_key,
        email,
        license_status,
        license_expiration,
        created_at,
        CASE 
            WHEN license_expiration > NOW() THEN 'VALID'
            ELSE 'EXPIRED'
        END as current_status,
        license_expiration - NOW() as time_remaining
    FROM users 
    WHERE license_key = %s
    """
    
    cursor.execute(query, (license_key,))
    result = cursor.fetchone()
    
    if result:
        print("\n" + "="*70)
        print("LICENSE DETAILS")
        print("="*70)
        print(f"License Key:        {result[0]}")
        print(f"Email:              {result[1]}")
        print(f"Status (DB):        {result[2]}")
        print(f"Created At:         {result[4]}")
        print(f"Expiration:         {result[3]}")
        print(f"Current Status:     {result[5]}")
        print(f"Time Remaining:     {result[6]}")
        print("="*70)
        
        # Check if there's a mismatch
        if result[5] == 'EXPIRED':
            print("\n⚠️  LICENSE IS EXPIRED!")
            print(f"   Expiration date: {result[3]}")
            print(f"   Current time:    {datetime.now()}")
        else:
            print("\n✅ LICENSE IS VALID")
            
    else:
        print(f"\n❌ License key {license_key} not found in database")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ Database error: {e}")
    print("\nMake sure:")
    print("1. DB_PASSWORD environment variable is set")
    print("2. PostgreSQL server is accessible from your IP")
    print("3. You have psycopg2 installed: pip install psycopg2-binary")
    print("\nAlternatively, use Azure CLI:")
    print("az webapp config appsettings list --name quotrading-flask-api --resource-group quotrading-rg")
