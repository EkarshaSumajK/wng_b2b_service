"""
Script to create b2b_user_sessions table for B2B user session management.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def create_b2b_user_sessions_table():
    """Create b2b_user_sessions table if it doesn't exist."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'b2b_user_sessions'
            )
        """))
        
        if result.scalar():
            print("Table 'b2b_user_sessions' already exists")
            return
        
        # Create the table
        print("Creating 'b2b_user_sessions' table...")
        conn.execute(text("""
            CREATE TABLE b2b_user_sessions (
                session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES b2b_users(user_id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                refresh_token_hash VARCHAR(255),
                device_info JSONB,
                ip_address INET,
                user_agent TEXT,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                is_revoked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX idx_b2b_user_sessions_user_id ON b2b_user_sessions(user_id);
            CREATE INDEX idx_b2b_user_sessions_expires_at ON b2b_user_sessions(expires_at);
            CREATE INDEX idx_b2b_user_sessions_token_hash ON b2b_user_sessions(token_hash);
        """))
        
        conn.commit()
        print("Successfully created 'b2b_user_sessions' table with indexes")

if __name__ == "__main__":
    create_b2b_user_sessions_table()
