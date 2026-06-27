
import hashlib
import sqlite3
import json

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
    
    # 🔥 Initialize caching table too!
    init_question_bank()

def create_user(username, password):
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        clean_user = username.strip()
        clean_pass = password.strip()
        
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (clean_user, clean_pass))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
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

# ==========================================
# 🧠 GLOBAL QUESTION BANK (CACHING SYSTEM)
# ==========================================

# ==========================================
# 🧠 GLOBAL QUESTION BANK WITH USER HISTORY
# ==========================================

def init_question_bank():
    conn = sqlite3.connect('heizen.db')
    c = conn.cursor()
    # Global Bank
    c.execute('''
        CREATE TABLE IF NOT EXISTS question_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            difficulty TEXT,
            question_data TEXT
        )
    ''')
    # 🔥 Naya Table: User ne kaun sa question dekh liya hai track karne ke liye
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_history (
            username TEXT,
            question_id INTEGER,
            PRIMARY KEY (username, question_id)
        )
    ''')
    conn.commit()
    conn.close()

def save_questions_to_bank(subject, topic, difficulty, questions_list, username):
    """Saves new questions to global bank and marks them as SEEN for the current user"""
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        clean_sub = subject.strip().lower()
        clean_top = topic.strip().lower()
        
        for q in questions_list:
            # 1. Save to Global Bank
            c.execute("INSERT INTO question_bank (subject, topic, difficulty, question_data) VALUES (?, ?, ?, ?)", 
                      (clean_sub, clean_top, difficulty, json.dumps(q)))
            new_q_id = c.lastrowid
            
            # 2. Automatically mark as SEEN for this specific user
            c.execute("INSERT OR IGNORE INTO user_history (username, question_id) VALUES (?, ?)", 
                      (username.strip(), new_q_id))
                      
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving to question bank: {e}")

def get_cached_questions(username, subject, topic, difficulty, num_questions):
    """Fetches questions from DB that the CURRENT USER HAS NOT SEEN YET"""
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        clean_sub = subject.strip().lower()
        clean_top = topic.strip().lower()
        
        # 🔥 Magic Query: NOT IN user_history ensures no duplicates for the same person
        c.execute('''
            SELECT id, question_data FROM question_bank 
            WHERE subject=? AND topic=? AND difficulty=? 
            AND id NOT IN (SELECT question_id FROM user_history WHERE username=?)
            ORDER BY RANDOM() LIMIT ?
        ''', (clean_sub, clean_top, difficulty, username.strip(), num_questions))
        
        rows = c.fetchall()
        
        if rows and len(rows) == num_questions:
            # Agar enough unseen questions mil gaye, toh unhe is user ke liye SEEN mark kar do
            for row in rows:
                c.execute("INSERT OR IGNORE INTO user_history (username, question_id) VALUES (?, ?)", 
                          (username.strip(), row[0]))
            conn.commit()
            conn.close()
            return [json.loads(row[1]) for row in rows]
            
        conn.close()
        return None # Agar unseen questions kam hain, toh Gemini naye generate karega
    except Exception as e:
        print(f"Cache fetch error: {e}")
        return None
def set_pro_status(username):
    """Marks a user as PRO in the database."""
    try:
        conn = sqlite3.connect('heizen.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_pro=1 WHERE username=?", (username.strip(),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting PRO status: {e}")
        return False        