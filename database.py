import sqlite3

def init_db():
    conn = sqlite3.connect('responses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            user_id INTEGER,
            category TEXT,
            question TEXT,
            answer TEXT,
            media BLOB
        )
    ''')
    conn.commit()
    conn.close()

def save_response(user_id, category, question, answer, media=None):
    conn = sqlite3.connect('responses.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO responses (user_id, category, question, answer, media)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, category, question, answer, media))
    conn.commit()
    conn.close()