import sqlite3
import os
from datetime import datetime
import logging
import re

DB_FILE = "email_assistant.db"

def init_db():
    """Initialize the database with required tables"""
    db_exists = os.path.exists(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        email TEXT,
        is_member INTEGER DEFAULT 1,
        is_deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_message TEXT,
        bot_reply TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chat_id) REFERENCES chats (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    if not db_exists:
        cursor.execute('''
        INSERT INTO users (name, phone, email, is_member) VALUES 
        ('Zain Raza', '+923065187343', 'zainxaidi2003@gmail.com', 1),
        ('John Doe', '+12345678901', 'john@example.com', 1),
        ('Jane Smith', '+12345678902', 'jane@example.com', 0)
        ''')
    
    conn.commit()
    conn.close()

def execute_query(query, params=None, fetch=True):
    """Execute an SQL query and return results if needed"""

    clean_query = query.strip()
    if clean_query.startswith("```"):
        # Remove SQL code block markers if present
        clean_query = clean_query.split("\n", 1)[-1]  
        if clean_query.endswith("```"):
            clean_query = clean_query.rsplit("\n", 1)[0] 
    
    # Clean up the query
    clean_query = clean_query.replace("`", "").strip().rstrip(';')
    clean_query = clean_query.replace("NOW()", "CURRENT_TIMESTAMP")
    clean_query = clean_query.replace("CURDATE()", "DATE('now')")
    
    # Log the cleaned query
    logging.debug(f"Executing SQL query: {clean_query}")
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  
    cursor = conn.cursor()
    
    try:
        if params:
            cursor.execute(clean_query, params)
        else:
            # For INSERT queries with text values, use parameterized queries
            if clean_query.upper().startswith("INSERT"):
                # Extract values from the query
                match = re.search(r"VALUES\s*\((.*?)\)", clean_query, re.IGNORECASE | re.DOTALL)
                if match:
                    # Get the values part
                    values = match.group(1)
                    # Split into individual values
                    value_list = [v.strip().strip("'") for v in values.split(",")]
                    # Create parameterized query
                    param_placeholders = ",".join(["?" for _ in value_list])
                    param_query = re.sub(
                        r"VALUES\s*\(.*?\)",
                        f"VALUES ({param_placeholders})",
                        clean_query,
                        flags=re.IGNORECASE | re.DOTALL
                    )
                    cursor.execute(param_query, value_list)
                else:
                    cursor.execute(clean_query)
            else:
                cursor.execute(clean_query)
        
        if fetch:
            if clean_query.strip().upper().startswith("SELECT"):
                results = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return results if results else []  # Return empty list instead of None
            else:
                conn.commit()
                last_id = cursor.lastrowid
                conn.close()
                return {"id": last_id}
        else:
            conn.commit()
            conn.close()
            return {"success": True}
    except Exception as e:
        logging.error(f"Database error: {str(e)}")
        conn.close()
        raise e 