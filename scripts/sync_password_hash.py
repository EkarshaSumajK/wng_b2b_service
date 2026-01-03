"""
Script to generate password_hash for b2b_users using bcrypt.
Uses email as the default password for each user.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Same password context as admin platform
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)

def generate_password_hashes():
    """Generate password_hash for all b2b_users using email as password."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Get all users without password_hash
        result = conn.execute(text("""
            SELECT user_id, email FROM b2b_users 
            WHERE password_hash IS NULL OR password_hash = ''
        """))
        users = result.fetchall()
        
        print(f"Found {len(users)} users without password_hash")
        
        updated = 0
        for user_id, email in users:
            # Use email as the default password
            password_hash = hash_password(email)
            
            conn.execute(text("""
                UPDATE b2b_users 
                SET password_hash = :password_hash
                WHERE user_id = :user_id
            """), {"password_hash": password_hash, "user_id": user_id})
            
            updated += 1
            if updated % 100 == 0:
                print(f"Updated {updated} users...")
        
        conn.commit()
        print(f"Successfully generated password_hash for {updated} users")
        print("Default password for each user is their email address")

if __name__ == "__main__":
    generate_password_hashes()
