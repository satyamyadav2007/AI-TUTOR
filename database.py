import sqlite3
import json
import hashlib

def init_db():
    conn = sqlite3.connect('heizen.db')
    c = conn.cursor()
    # Base Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            elo INTEGER DEFAULT 1200,
            weak_topics TEXT DEFAULT '{}'
        )
    ''')
    
    # Safely add new columns one by one
    try:
        c.execute("ALTER TABLE users ADD COLUMN generations_used INTEGER DEFAULT 0")
    except:
        pass 
        
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_pro BOOLEAN DEFAULT 0")
    except:
        pass
        
    conn.commit()
    conn.close()

def create_user(username, password):
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        # .strip() removes any accidental invisible spaces
        clean_user = username.strip()
        clean_pass = password.strip()
        
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (clean_user, clean_pass))
        conn.commit() # 🔥 MOST CRITICAL LINE: Saves data permanently
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # User already exists
        return False
    except Exception as e:
        print(f"Error creating user: {e}")
        return False

def login_user(username, password):
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        
        clean_user = username.strip()
        clean_pass = password.strip()
        
        c.execute("SELECT elo, weak_topics, generations_used, is_pro FROM users WHERE username=? AND password=?", (clean_user, clean_pass))
        user = c.fetchone()
        conn.close()
        
        if user:
            # Safely parse JSON and handle missing data
            weak_data = {}
            if user[1]:
                try:
                    weak_data = json.loads(user[1])
                except:
                    pass

            return {
                "elo": user[0], 
                "weak_topics": weak_data,
                "generations_used": user[2] if user[2] is not None else 0,
                "is_pro": bool(user[3]) if user[3] is not None else False
            }
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

def update_user_progress(username, new_elo, weak_topics):
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        c.execute("UPDATE users SET elo=?, weak_topics=? WHERE username=?", 
                  (new_elo, json.dumps(weak_topics), username.strip()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Progress Update Error: {e}")

def increment_usage(username):
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        c.execute("UPDATE users SET generations_used = generations_used + 1 WHERE username=?", (username.strip(),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Usage Increment Error: {e}")