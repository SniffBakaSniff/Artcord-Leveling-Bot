import sqlite3

from bot import main2
message_db_path = main2.message_db_path

def init_db():
    with sqlite3.connect(message_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp DATETIME
            );
        ''')
    conn.commit()

if __name__ == '__main__':
    init_db()
