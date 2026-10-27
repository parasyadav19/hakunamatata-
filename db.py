from datetime import date
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("PGHOST"),
    "dbname": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "sslmode": os.getenv("PGSSLMODE", "require"),
    "channel_binding": os.getenv("PGCHANNELBINDING", "prefer"),
}

def get_db():
    return psycopg.connect(**DB_CONFIG)


def init_db():
    conn = get_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    rollno VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100),
                    role VARCHAR(20),
                    branch VARCHAR(50),
                    year VARCHAR(20)
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    rollno VARCHAR(50) REFERENCES students(rollno),
                    date DATE NOT NULL,
                    time TIME NOT NULL,
                    status VARCHAR(20),
                    UNIQUE (rollno, date)
                )
            """)

        conn.commit()
        print("Tables ready - 1 Day 1 Attendance Locked!")

    finally:
        conn.close()


def save_student(rollno, name, role, branch, year):
    conn = get_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO students (rollno, name, role, branch, year)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (rollno)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    branch = EXCLUDED.branch,
                    year = EXCLUDED.year
            """, (rollno, name, role, branch, year))

        conn.commit()

    finally:
        conn.close()


def get_all_students():
    conn = get_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rollno, name, role, branch, year
                FROM students
                ORDER BY rollno
            """)

            columns = [desc.name for desc in cur.description]
            data = [dict(zip(columns, row)) for row in cur.fetchall()]

        return data

    finally:
        conn.close()


def mark_attendance_db(rollno):
    conn = get_db()
    today = date.today()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO attendance (rollno, date, time, status)
                VALUES (%s, CURRENT_DATE, LOCALTIME, 'Present')
                ON CONFLICT (rollno, date) DO NOTHING
                RETURNING id
            """, (rollno,))

            saved = cur.fetchone()

        conn.commit()

        if saved:
            print(f"SAVED - {rollno} on {today}")
            return True

        print(f"BLOCKED - Already marked today: {rollno} on {today}")
        return False

    finally:
        conn.close()