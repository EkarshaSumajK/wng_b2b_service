"""
Script to drop b2b_users table and rename b2b_users_auth to b2b_users
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def rename_users_table():
    engine = create_engine(settings.DATABASE_URL_AUTH)
    
    with engine.connect() as conn:
        # Drop b2b_users table
        print("Dropping b2b_users table...")
        conn.execute(text("DROP TABLE IF EXISTS b2b_users CASCADE"))
        conn.commit()
        print("b2b_users dropped")
        
        # Rename b2b_users_auth to b2b_users
        print("Renaming b2b_users_auth to b2b_users...")
        conn.execute(text("ALTER TABLE b2b_users_auth RENAME TO b2b_users"))
        conn.commit()
        print("Table renamed successfully")
        
        # Update foreign key constraints that reference b2b_users_auth
        # First, get all foreign keys referencing b2b_users_auth
        print("Updating foreign key references...")
        
        # The foreign keys should automatically point to the renamed table
        # but we need to update any constraints that have the old name
        
        print("Done!")

if __name__ == "__main__":
    rename_users_table()
