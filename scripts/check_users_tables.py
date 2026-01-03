"""
Script to check users in both users and b2b_users tables.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def check_users():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check users table
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        users_count = result.scalar()
        print(f"Users in 'users' table: {users_count}")
        
        # Check b2b_users table
        result = conn.execute(text("SELECT COUNT(*) FROM b2b_users"))
        b2b_users_count = result.scalar()
        print(f"Users in 'b2b_users' table: {b2b_users_count}")
        
        # Sample from users
        result = conn.execute(text("SELECT email, username FROM users LIMIT 5"))
        print("\nSample from 'users' table:")
        for row in result:
            print(f"  {row[0]} ({row[1]})")
        
        # Sample from b2b_users
        result = conn.execute(text("SELECT email, display_name FROM b2b_users LIMIT 5"))
        print("\nSample from 'b2b_users' table:")
        for row in result:
            print(f"  {row[0]} ({row[1]})")

if __name__ == "__main__":
    check_users()
