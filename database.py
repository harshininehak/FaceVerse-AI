import sqlite3


def get_connection():
    return sqlite3.connect("database/facerecognition.db")


def create_tables():

    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            userid TEXT UNIQUE,
            email TEXT,
            phone TEXT,
            age INTEGER,
            gender TEXT
        )
    """)

    # Login History table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            userid TEXT,
            name TEXT,
            login_date TEXT,
            login_time TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


create_tables()