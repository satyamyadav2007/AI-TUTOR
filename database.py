import sqlite3
import json
import hashlib

# Database initialize karne ka function
def init_db():
    conn = sqlite3.connect('heizen_users.db')
    c = conn.cursor()
    # Users table create karein agar pehle se nahi hai
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, elo INTEGER, weak_topics TEXT)''')
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
    conn = sqlite3.connect('heizen_users.db')
    c = conn.cursor()
    c.execute("SELECT elo, weak_topics FROM users WHERE username=? AND password=?", 
              (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {"elo": user[0], "weak_topics": json.loads(user[1])}
    return None # Login failed

# Exam ke baad user ka data (ELO & mistakes) update karne ka function
def update_user_progress(username, elo, weak_topics):
    conn = sqlite3.connect('heizen_users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET elo=?, weak_topics=? WHERE username=?", 
              (elo, json.dumps(weak_topics), username))
    conn.commit()
    conn.close()