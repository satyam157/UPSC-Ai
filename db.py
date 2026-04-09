import psycopg2
import os
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

conn = None

def get_connection():
    try:
        try:
            if "DATABASE_URL" in st.secrets:
                return psycopg2.connect(st.secrets["DATABASE_URL"])
        except Exception:
            pass

        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return psycopg2.connect(db_url)

        connection = psycopg2.connect(
            dbname=os.getenv("PG_DB", "postgres"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", "postgres"),
            host=os.getenv("PG_HOST", "localhost"),
            port=os.getenv("PG_PORT", "5432")
        )
        return connection
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

try:
    conn = get_connection()
    if conn:
        with conn.cursor() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                title TEXT, 
                content TEXT, 
                date TEXT
            )
            """)

            c.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                question TEXT
            )
            """)

            c.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                name TEXT, 
                total INT, 
                attempted INT,
                correct INT, 
                wrong INT, 
                accuracy REAL, 
                marks REAL
            )
            """)

            c.execute("""
            CREATE TABLE IF NOT EXISTS saved_items (
                id SERIAL PRIMARY KEY,
                item_type TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            c.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                username TEXT PRIMARY KEY,
                retention_days INT
            )
            """)

            # CA Filter words table
            c.execute("""
            CREATE TABLE IF NOT EXISTS ca_filters (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # AI Analysis Reports table
            c.execute("""
            CREATE TABLE IF NOT EXISTS ai_reports (
                id SERIAL PRIMARY KEY,
                report_type TEXT,
                period_label TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

            # Test Paper Analysis table
            c.execute("""
            CREATE TABLE IF NOT EXISTS test_papers (
                id SERIAL PRIMARY KEY,
                test_name TEXT,
                test_date DATE DEFAULT CURRENT_DATE,
                total_questions INT,
                attempted INT,
                not_attempted INT,
                guessed_correct INT,
                guessed_incorrect INT,
                carelessness_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)

        conn.commit()
except Exception as e:
    print(f"Error initializing DB schemas: {e}")

# ── NEWS ──────────────────────────────────────────────────────────────────────

def insert_news(news):
    if not conn: return
    try:
        with conn.cursor() as c:
            for n in news:
                c.execute("INSERT INTO news (title, content, date) VALUES (%s, %s, %s)", (n["title"], n["content"], n["date"]))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()

def get_news():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT title, content, date FROM news")
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def save_question(q):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO questions (question) VALUES (%s)", (q,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

def get_questions():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT question FROM questions")
            return [x[0] for x in c.fetchall()]
    except Exception as e:
        print(e)
        return []

# ── RESULTS ───────────────────────────────────────────────────────────────────

def save_result(data):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO results (name, total, attempted, correct, wrong, accuracy, marks) VALUES (%s, %s, %s, %s, %s, %s, %s)", data)
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

def get_results():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, name, total, attempted, correct, wrong, accuracy, marks FROM results")
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def delete_result(rowid):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM results WHERE id = %s", (rowid,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

# ── SAVED ITEMS ───────────────────────────────────────────────────────────────

def save_item(item_type, content):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO saved_items (item_type, content) VALUES (%s, %s)", (item_type, content))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

def get_saved_items():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, item_type, content, timestamp FROM saved_items ORDER BY timestamp DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def delete_saved_item(item_id):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM saved_items WHERE id = %s", (item_id,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

def clean_old(days=15):
    if not conn: return
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with conn.cursor() as c:
            c.execute("DELETE FROM news WHERE date < %s", (cutoff,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

# ── USER SETTINGS ─────────────────────────────────────────────────────────────

def get_retention(username):
    if not conn: return 15
    try:
        with conn.cursor() as c:
            c.execute("SELECT retention_days FROM user_settings WHERE username = %s", (username,))
            res = c.fetchone()
            if res:
                return res[0]
            return 15
    except Exception as e:
        print(e)
        return 15

def set_retention(username, days):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("""
            INSERT INTO user_settings (username, retention_days)
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE 
            SET retention_days = EXCLUDED.retention_days
            """, (username, days))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

# ── CA FILTERS ────────────────────────────────────────────────────────────────

def add_ca_filter(word):
    if not conn: return False
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO ca_filters (word) VALUES (%s) ON CONFLICT (word) DO NOTHING", (word.lower().strip(),))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        conn.rollback()
        return False

def get_ca_filters():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, word FROM ca_filters ORDER BY word")
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def delete_ca_filter(filter_id):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ca_filters WHERE id = %s", (filter_id,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

# ── AI REPORTS ────────────────────────────────────────────────────────────────

def save_ai_report(report_type, period_label, content):
    if not conn: return None
    try:
        with conn.cursor() as c:
            c.execute(
                "INSERT INTO ai_reports (report_type, period_label, content) VALUES (%s, %s, %s) RETURNING id",
                (report_type, period_label, content)
            )
            new_id = c.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        print(e)
        conn.rollback()
        return None

def get_ai_reports():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, report_type, period_label, content, created_at FROM ai_reports ORDER BY created_at DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def delete_ai_report(report_id):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ai_reports WHERE id = %s", (report_id,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()

# ── TEST PAPERS ───────────────────────────────────────────────────────────────

def save_test_paper(test_name, test_date, total_questions, attempted, not_attempted,
                    guessed_correct, guessed_incorrect, carelessness_notes):
    if not conn: return None
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO test_papers 
                (test_name, test_date, total_questions, attempted, not_attempted,
                 guessed_correct, guessed_incorrect, carelessness_notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (test_name, test_date, total_questions, attempted, not_attempted,
                  guessed_correct, guessed_incorrect, carelessness_notes))
            new_id = c.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        print(e)
        conn.rollback()
        return None

def get_test_papers():
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, test_name, test_date, total_questions, attempted, not_attempted,
                       guessed_correct, guessed_incorrect, carelessness_notes, created_at
                FROM test_papers ORDER BY test_date DESC, created_at DESC
            """)
            return c.fetchall()
    except Exception as e:
        print(e)
        return []

def delete_test_paper(paper_id):
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM test_papers WHERE id = %s", (paper_id,))
        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()
