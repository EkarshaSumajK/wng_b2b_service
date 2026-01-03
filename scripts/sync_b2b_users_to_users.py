"""
Script to sync b2b_users to admin platform's users table.
This allows B2B users to authenticate via admin platform.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def sync_users():
    """Sync b2b_users to users table for admin platform authentication."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Get b2b_users that don't exist in users table
        result = conn.execute(text("""
            SELECT b.user_id, b.email, b.display_name, b.password_hash, b.role, b.created_at
            FROM b2b_users b
            LEFT JOIN users u ON b.email = u.email
            WHERE u.user_id IS NULL
        """))
        users_to_sync = result.fetchall()
        
        print(f"Found {len(users_to_sync)} b2b_users to sync to users table")
        
        synced = 0
        for user_id, email, display_name, password_hash, role, created_at in users_to_sync:
            # Generate username from email
            username = email.split("@")[0].lower().replace(".", "_").replace("-", "_")
            
            # Check if username exists
            result = conn.execute(text(
                "SELECT COUNT(*) FROM users WHERE username = :username"
            ), {"username": username})
            if result.scalar() > 0:
                # Add suffix to make unique
                username = f"{username}_{str(user_id)[:8]}"
            
            # Map B2B role to admin platform role
            role_map = {
                "COUNSELLOR": "moderator",
                "TEACHER": "moderator", 
                "PRINCIPAL": "admin",
                "PARENT": "moderator",
                "CLINICIAN": "moderator",
                "ADMIN": "admin"
            }
            admin_role = role_map.get(role, "moderator")
            
            # Insert into users table
            conn.execute(text("""
                INSERT INTO users (user_id, username, email, password_hash, full_name, role, is_active, email_verified, created_at, updated_at)
                VALUES (:user_id, :username, :email, :password_hash, :full_name, :role, true, true, :created_at, NOW())
            """), {
                "user_id": user_id,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "full_name": display_name,
                "role": admin_role,
                "created_at": created_at
            })
            
            synced += 1
            if synced % 100 == 0:
                print(f"Synced {synced} users...")
        
        conn.commit()
        print(f"Successfully synced {synced} users to users table")
        
        # Verify
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        print(f"Total users in 'users' table now: {result.scalar()}")

if __name__ == "__main__":
    sync_users()
