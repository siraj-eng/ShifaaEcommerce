#!/usr/bin/env python3
"""
Database migration script to add missing columns to users table
"""

import sqlite3
import os

def migrate_database():
    """Add missing phone and address columns to users table"""
    
    db_path = os.path.join(os.path.dirname(__file__), 'shifaa.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database...")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if phone column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'phone' not in columns:
            print("Adding phone column...")
            cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
        
        if 'address' not in columns:
            print("Adding address column...")
            cursor.execute("ALTER TABLE users ADD COLUMN address TEXT")
        
        if 'created_at' not in columns:
            print("Adding created_at column...")
            cursor.execute("ALTER TABLE users ADD COLUMN created_at DATETIME")
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
