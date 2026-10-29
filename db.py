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
            cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;")
            cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;")
            cur.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS distance_meters DOUBLE PRECISION;")
        conn.commit()
        print("Tables ready - 1 Day 1 Attendance Locked + Geo Added!")
    finally:
        conn.close()

def save_student(rollno, name, role, branch, year):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            # FIX: Pehle check kar already hai kya, warna overwrite ho jayega
            cur.execute("SELECT rollno FROM students WHERE rollno = %s", (rollno,))
            if cur.fetchone():
                return False  # Already exists
            
            cur.execute("""
                INSERT INTO students (rollno, name, role, branch, year)
                VALUES (%s, %s, %s, %s, %s)
            """, (rollno, name, role, branch, year))
        conn.commit()
        return True
    finally:
        conn.close()

def mark_attendance_db(rollno, latitude=None, longitude=None, distance=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO attendance (rollno, date, time, status, latitude, longitude, distance_meters)
                VALUES (%s, CURRENT_DATE, LOCALTIME, 'Present', %s, %s, %s)
                ON CONFLICT (rollno, date) DO NOTHING RETURNING id
            """, (rollno, latitude, longitude, distance))
            saved = cur.fetchone()
        conn.commit()
        return True if saved else False
    finally:
        conn.close()

def get_todays_attendance_for_excel(target_date):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.rollno, s.name, s.branch, s.year, a.date, a.time, a.status, a.latitude, a.longitude, a.distance_meters
                FROM attendance a JOIN students s ON a.rollno = s.rollno
                WHERE a.date = %s ORDER BY a.time ASC
            """, (target_date,))
            columns = [desc.name for desc in cur.description]
            data = [dict(zip(columns, row)) for row in cur.fetchall()]
        return data
    finally:
        conn.close()