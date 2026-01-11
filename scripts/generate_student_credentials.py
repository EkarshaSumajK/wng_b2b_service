"""
Script to generate username and password for all B2B students.

Username format: firstname.lastname (lowercase, no spaces)
- If duplicate, append number: firstname.lastname2, firstname.lastname3, etc.

Password format: FirstnameLastname@123 (capitalized first letters)
"""

import psycopg2
from passlib.context import CryptContext
import re
from collections import defaultdict

# Password hashing
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# Database connection
DB_URL = "postgresql://neondb_owner:npg_mBKi4vraL5EX@ep-nameless-flower-ah3bcrfe-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"


def clean_name(name: str) -> str:
    """Clean name for username generation."""
    if not name:
        return ""
    # Remove special characters, keep only alphanumeric
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    return cleaned


def generate_username(first_name: str, last_name: str, existing_usernames: set) -> str:
    """Generate unique username from first and last name."""
    first = clean_name(first_name)
    last = clean_name(last_name)
    
    if not first:
        first = "student"
    if not last:
        last = "user"
    
    base_username = f"{first}.{last}"
    username = base_username
    
    # If username exists, append number
    counter = 2
    while username in existing_usernames:
        username = f"{base_username}{counter}"
        counter += 1
    
    return username


def generate_password(first_name: str, last_name: str) -> str:
    """Generate password from first and last name."""
    first = (first_name or "Student").strip().capitalize()
    last = (last_name or "User").strip().capitalize()
    return f"{first}{last}@123"


def main():
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Get all students without username
    cur.execute("""
        SELECT student_id, first_name, last_name, username 
        FROM b2b_students 
        WHERE username IS NULL OR password_hash IS NULL
        ORDER BY first_name, last_name
    """)
    students = cur.fetchall()
    
    print(f"Found {len(students)} students to update")
    
    if not students:
        print("No students need updating.")
        cur.close()
        conn.close()
        return
    
    # Get existing usernames to avoid duplicates
    cur.execute("SELECT username FROM b2b_students WHERE username IS NOT NULL")
    existing_usernames = {row[0] for row in cur.fetchall()}
    print(f"Existing usernames: {len(existing_usernames)}")
    
    # Generate credentials for each student
    updates = []
    credentials_log = []
    
    for student_id, first_name, last_name, current_username in students:
        username = generate_username(first_name, last_name, existing_usernames)
        existing_usernames.add(username)  # Track new username
        
        password = generate_password(first_name, last_name)
        password_hash = pwd_context.hash(password)
        
        updates.append((username, password_hash, student_id))
        credentials_log.append({
            "student_id": str(student_id),
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "password": password,
        })
    
    # Preview first 10
    print("\nPreview (first 10):")
    print("-" * 80)
    for cred in credentials_log[:10]:
        print(f"  {cred['first_name']} {cred['last_name']} -> username: {cred['username']}, password: {cred['password']}")
    print("-" * 80)
    
    # Confirm before updating
    confirm = input(f"\nUpdate {len(updates)} students? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Aborted.")
        cur.close()
        conn.close()
        return
    
    # Update database
    print("\nUpdating database...")
    updated = 0
    for username, password_hash, student_id in updates:
        try:
            cur.execute("""
                UPDATE b2b_students 
                SET username = %s, password_hash = %s 
                WHERE student_id = %s
            """, (username, password_hash, student_id))
            updated += 1
        except Exception as e:
            print(f"Error updating {student_id}: {e}")
    
    conn.commit()
    print(f"\nUpdated {updated} students successfully!")
    
    # Save credentials to file for reference
    import json
    with open('student_credentials.json', 'w') as f:
        json.dump(credentials_log, f, indent=2)
    print("Credentials saved to student_credentials.json")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
