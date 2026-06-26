import sqlite3
import json
import hashlib

# Database initialize karne ka function
def init_db():
    conn = sqlite3.connect('heizen.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            elo INTEGER DEFAULT 1200,
            weak_topics TEXT DEFAULT '{}'
        )
    ''')
    # Naye columns add karne ka safe tarika (agar table pehle se bani ho)
    try:
        c.execute("ALTER TABLE users ADD COLUMN generations_used INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN is_pro BOOLEAN DEFAULT 0")
    except:
        pass # Agar columns already hain, toh error ignore karega
        
    conn.commit()
    conn.close()

# Password ko secure banane ke liye hash function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Naya user (Signup) create karne ka function
def create_user(username, password):
    conn = sqlite3.connect('heizen_users.db')
    c = conn.cursor()
    try:
        # Default ELO 1200 aur empty weak_topics set karenge
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", 
                  (username, hash_password(password), 1200, '{}'))
        conn.commit()
        return True # Signup successful
    except sqlite3.IntegrityError:
        return False # Username pehle se exist karta hai
    finally:
        conn.close()

# Login verify karne ka function
def login_user(username, password):
    conn = sqlite3.connect('heizen.db')
    c = conn.cursor()
    c.execute("SELECT elo, weak_topics, generations_used, is_pro FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {
            "elo": user[0], 
            "weak_topics": json.loads(user[1]),
            "generations_used": user[2] if user[2] is not None else 0,
            "is_pro": bool(user[3]) if user[3] is not None else False
        }
    return None

# Exam ke baad user ka data (ELO & mistakes) update karne ka function
def update_user_progress(username, elo, weak_topics):
    conn = sqlite3.connect('heizen_users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET elo=?, weak_topics=? WHERE username=?", 
              (elo, json.dumps(weak_topics), username))
    conn.commit()
    conn.close()
def increment_usage(username):
    """User jab bhi kuch generate karega, uska counter 1 se badha dega"""
    conn = sqlite3.connect('heizen.db')
    c = conn.cursor()
    c.execute("UPDATE users SET generations_used = generations_used + 1 WHERE username=?", (username,))
    conn.commit()
    conn.close()    