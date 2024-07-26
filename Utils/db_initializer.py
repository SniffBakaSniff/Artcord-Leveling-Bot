import sqlite3, os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'database.db')

def init_db():
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                nickname TEXT NOT NULL,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                avatar_url TEXT,
                xp_needed INTEGER DEFAULT 100,
                total_xp INTEGER DEFAULT 0,
                card_bg_color TEXT DEFAULT '#2b2b2b55',
                card_bg_img_url TEXT DEFAULT 'http://127.0.0.1:5000/images/background.jpg',
                card_text_color TEXT DEFAULT 'white',
                card_progress_bar_color TEXT DEFAULT '#00f0b4'
            );
        ''')

        cursor.execute('''  
            CREATE TABLE IF NOT EXISTS pookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                access_level INTEGER DEFAULT 1
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_data (
                guild_id TEXT PRIMARY KEY,
                guild_name TEXT NOT NULL,
                channel_ids TEXT,
                channel_names TEXT,
                role_ids TEXT,
                role_names TEXT
            );
        ''')

        cursor.execute('SELECT COUNT(*) FROM pookies')
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.execute('''
                INSERT INTO pookies (username, password, access_level)
                VALUES ('Secret', 'Secret', 2)
            ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                username TEXT NOT NULL,
                success BOOLEAN,
                message TEXT
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                level INTEGER,
                role_id TEXT,
                xp_modifier REAL DEFAULT 1.0
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY,
                api_key TEXT UNIQUE,
                permissions TEXT
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quests (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL,  -- daily or weekly
                description TEXT NOT NULL,
                task_type TEXT NOT NULL,
                goal INTEGER NOT NULL,
                xp_reward INTEGER NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_quests (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                quest_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Add last_updated column
                FOREIGN KEY (quest_id) REFERENCES quests (id)
            );
        ''')

        cursor.execute('SELECT COUNT(*) FROM api_keys')
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.execute('INSERT INTO api_keys (api_key, permissions) VALUES (?, ?)', ('Secret', 'Secret'))
            print("Inserted default API key")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                min_xp INTEGER DEFAULT 1,
                max_xp INTEGER DEFAULT 5,
                level_notif_id TEXT DEFAULT "Set Id using website",
                inactive_channel_id TEXT DEFAULT "Set Id using website"
            );
        ''')

        cursor.execute('SELECT COUNT(*) FROM settings')
        count = cursor.fetchone()[0]

        if count == 0:
            cursor.execute('''
                INSERT INTO settings (min_xp, max_xp)
                VALUES (1, 5)
            ''')

        conn.commit()

if __name__ == '__main__':
    init_db()
