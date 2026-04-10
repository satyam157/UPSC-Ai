import psycopg2
import os
import streamlit as st
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ── Schema init guard: only run once per process ──────────────────────────────
_schema_initialized = False


def get_connection():
    """Get a fresh database connection with proper error handling."""
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

def _safe_rollback(connection):
    """Safely rollback a connection if still open."""
    if connection:
        try:
            if not connection.closed:
                connection.rollback()
        except Exception:
            pass

def _init_schema(connection):
    """Initialize database schema."""
    if not connection:
        return
    try:
        with connection.cursor() as cur:
            cur.execute("SET statement_timeout = 60000")
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    source TEXT,
                    category TEXT,
                    date TEXT
                )
            """)
            # Ensure columns exist if table was already created
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS url TEXT")
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS source TEXT")
            cur.execute("ALTER TABLE news ADD COLUMN IF NOT EXISTS category TEXT")
            # Fix duplicates before creating unique index
            cur.execute("DELETE FROM news a USING news b WHERE a.id < b.id AND a.title = b.title")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS news_title_uq ON news (title)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    question TEXT
                )
            """)

            cur.execute("""
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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS saved_items (
                    id SERIAL PRIMARY KEY,
                    item_type TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    username TEXT PRIMARY KEY,
                    retention_days INT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ca_filters (
                    id SERIAL PRIMARY KEY,
                    word TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Cleanup duplicates in filters
            cur.execute("DELETE FROM ca_filters a USING ca_filters b WHERE a.id < b.id AND a.word = b.word")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ca_filters_word_uq ON ca_filters (word)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_reports (
                    id SERIAL PRIMARY KEY,
                    report_type TEXT,
                    period_label TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
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
            
            # URL Summaries (Article Summarizer)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS url_summaries (
                    id SERIAL PRIMARY KEY,
                    url VARCHAR(1000) UNIQUE,
                    title VARCHAR(500),
                    subject VARCHAR(250),
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Syllabus Quizzes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS syllabus_quizzes (
                    id SERIAL PRIMARY KEY,
                    subject VARCHAR(250),
                    source VARCHAR(100),
                    questions JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Syllabus Quiz Attempts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS syllabus_quiz_attempts (
                    id SERIAL PRIMARY KEY,
                    quiz_id INTEGER,
                    user_answers JSONB,
                    score INTEGER,
                    percentage INTEGER,
                    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (quiz_id) REFERENCES syllabus_quizzes(id) ON DELETE CASCADE
                )
            """)

            # System Config table for global settings
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Users table for authentication
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
                    has_news_access BOOLEAN DEFAULT FALSE,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Ensure has_news_access column exists on older schemas
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS has_news_access BOOLEAN DEFAULT FALSE")

            # News access requests table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news_access_requests (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    status TEXT DEFAULT 'pending',
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP
                )
            """)
            
            # Enable RLS on all tables to satisfy security advisors
            tables = [
                'news', 'questions', 'results', 'saved_items', 'user_settings', 
                'ca_filters', 'ai_reports', 'test_papers', 'url_summaries', 
                'syllabus_quizzes', 'syllabus_quiz_attempts', 'system_config', 
                'users', 'news_access_requests'
            ]
            for table in tables:
                try:
                    cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
                except Exception:
                    pass
        
        connection.commit()
        _seed_default_users(connection)
    except Exception as e:
        _safe_rollback(connection)
        print(f"Schema initialization error: {e}")

def get_conn():
    """Get a fresh database connection, initializing schema only once per process."""
    global _schema_initialized
    conn = get_connection()
    if not conn:
        return None
    try:
        # Test connection is alive
        with conn.cursor() as c:
            c.execute("SELECT 1")
        conn.commit()
        # Initialize schema only once per process (not on every call)
        if not _schema_initialized:
            _init_schema(conn)
            _schema_initialized = True
        return conn
    except Exception as e:
        print(f"Connection check failed: {e}")
        _safe_rollback(conn)
        return None

def init_db():
    """Public interface to initialize the database (called by app.py)."""
    return get_conn()

# ── NEWS ──────────────────────────────────────────────────────────────────────

def insert_news(news):
    """Insert news items using executemany for efficiency."""
    if not news:
        return 0
    
    conn = get_connection()
    if not conn:
        return 0
    
    inserted_count = 0
    try:
        with conn.cursor() as c:
            # Prepare data for executemany
            data = [
                (n.get("title", ""), n.get("content", ""), n.get("url", ""), n.get("source", ""), n.get("category", "General"), n.get("date", ""))
                for n in news
            ]
            
            # executemany is more efficient than looping
            c.executemany(
                """
                INSERT INTO news (title, content, url, source, category, date)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (title) DO NOTHING
                """,
                data
            )
            inserted_count = c.rowcount
        
        conn.commit()
        return inserted_count
    except Exception as e:
        print(f"Insert error: {e}")
        _safe_rollback(conn)
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def get_news():
    """Retrieve recent news from database, ordered by date (newest first). Limit is configurable via system_config."""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        # Read configurable display limit (default 600)
        display_limit = 600
        try:
            cfg_val = get_config("news_display_limit", "600")
            display_limit = int(cfg_val)
        except (ValueError, TypeError):
            pass
        
        with conn.cursor() as c:
            # Retrieve all relevant news fields including category
            c.execute("SELECT title, content, date, url, source, category FROM news ORDER BY date DESC, id DESC LIMIT %s", (display_limit,))
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving news: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_news_by_date(target_date_str: str):
    """
    Retrieve news for a specific date from the database.
    
    Parameters
    ----------
    target_date_str : str
        Date string in 'YYYY-MM-DD' format.
    
    Returns
    -------
    List of tuples: (title, content, date, url, source, category)
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT title, content, date, url, source, category FROM news "
                "WHERE date LIKE %s ORDER BY date DESC, id DESC",
                (f"{target_date_str}%",)
            )
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving news by date: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_available_news_dates():
    """
    Get all unique dates that have news in the database.
    Returns a list of date strings (YYYY-MM-DD) sorted newest first.
    """
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT DISTINCT SUBSTRING(date FROM 1 FOR 10) AS d "
                "FROM news WHERE date IS NOT NULL AND date != '' "
                "ORDER BY d DESC LIMIT 90"
            )
            return [row[0] for row in c.fetchall()]
    except Exception as e:
        print(f"Error retrieving news dates: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_news_with_ids():
    """
    Like get_news() but includes the primary key `id` as the first column.
    Used by the DB audit so noise can be purged safely by PK.

    Returns rows: (id, title, content, date, url, source, category)
    """
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, title, content, date, url, source, category "
                "FROM news ORDER BY date DESC, id DESC LIMIT 600"
            )
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving news with IDs: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_news_by_ids(ids: list) -> int:
    """
    Delete news articles by their primary key IDs.
    Returns the number of rows actually deleted.

    This is safer than deleting by title (avoids accidental multi-row deletes
    when two articles share identical truncated titles).
    """
    if not ids:
        return 0

    conn = get_connection()
    if not conn:
        return 0

    try:
        with conn.cursor() as c:
            # Use a single parameterised IN query for efficiency
            placeholders = ",".join(["%s"] * len(ids))
            c.execute(f"DELETE FROM news WHERE id IN ({placeholders})", ids)
            deleted = c.rowcount
        conn.commit()
        return deleted
    except Exception as e:
        print(f"Error deleting news by IDs: {e}")
        _safe_rollback(conn)
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def trim_news_to_max(max_per_day: int = None) -> int:
    """
    Smart trim: enforce configurable news limit PER DAY in the database.

    POLICY:
      - Editorials/Explained/Opinion are NEVER trimmed (exempt from cap).
      - PIB + regular news are scored and only top `max_per_day` kept FOR EACH DATE.
      - Duplicate-looking articles (by title similarity) are always removed globally.

    Called automatically after each news fetch to prevent DB bloat and
    ensure only high-value content remains for reading.
    
    The max_per_day value defaults to the admin-configured value from system_config
    (key: 'news_max_per_day'), falling back to 40 if not set.

    Returns the number of articles deleted.
    """
    if max_per_day is None:
        try:
            cfg_val = get_config("news_max_per_day", "40")
            max_per_day = int(cfg_val)
        except (ValueError, TypeError):
            max_per_day = 40
    conn = get_connection()
    if not conn:
        return 0

    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT id, title, content, source, category, date "
                "FROM news ORDER BY date DESC, id DESC"
            )
            all_news = c.fetchall()

        if not all_news:
            return 0

        editorial_cats = {"editorial", "explained", "opinion", "lead", "op-ed", "governance", "pib"}
        editorial_sources = {
            "the hindu editorial", "the hindu opinion", "the hindu lead", "the hindu op-ed",
            "ie explained", "indian express opinion",
            "bs editorial", "livemint editorial", 
            "the wire", "the print", "down to earth", "pib",
        }

        # ─── SOURCE PRIORITY ─────────────────────────────────────────────────────────
        # Higher rank (lower number) = Higher priority
        # Priority order for Regular News (Hindu > IE > Livemint > Wire > Print > BS > DTE)
        SOURCE_PRIORITY_MAP = {
            "the hindu": 1, 
            "indian express": 2, 
            "livemint": 3,
            "the wire": 4, 
            "the print": 5,
            "business standard": 6, 
            "down to earth": 7,
            "pib": 8,
        }

        def get_source_rank(source_label):
            sl = str(source_label or "").lower()
            for key, rank in SOURCE_PRIORITY_MAP.items():
                if key in sl: return rank
            return 100

        # ── Group by Date ───────────────────────────────────────────────────
        news_by_date = {}
        for row in all_news:
            full_date = str(row[5])
            date_part = full_date.split(" ")[0] if " " in full_date else full_date
            if date_part not in news_by_date:
                news_by_date[date_part] = []
            news_by_date[date_part].append(row)

        ids_to_delete = []
        for date_val, day_news in news_by_date.items():
            day_editorials = []
            day_explained = []
            day_pib = []
            day_regular = []

            for row in day_news:
                news_id, title, content, source, category, _ = row
                cat_l = (category or "").lower()
                src_l = (source or "").lower()

                if "explained" in cat_l or "explained" in src_l:
                    day_explained.append(row)
                elif cat_l in {"editorial", "opinion", "lead", "op-ed", "governance"} or src_l in editorial_sources:
                    day_editorials.append(row)
                elif "pib" in cat_l or "pib" in src_l:
                    day_pib.append(row)
                else:
                    day_regular.append(row)

            def cap_rows(rows, target, maximum):
                if not rows or len(rows) <= target: return []
                # Priority 1: Source Rank (Lower is better)
                # Priority 2: ID DESC (Newer is better)
                rows.sort(key=lambda x: (get_source_rank(x[3]), -x[0]))
                to_del = [r[0] for r in rows[maximum:]]
                return to_del

            # Per-day limits: PIB (Target 10, Max 15), Regular (Target 30, Max 50), Explained (Target 15, Max 20), Editorials (Max 25)
            ids_to_delete.extend(cap_rows(day_pib, 10, 15))
            ids_to_delete.extend(cap_rows(day_regular, 30, 50))
            ids_to_delete.extend(cap_rows(day_explained, 15, 20))
            ids_to_delete.extend(cap_rows(day_editorials, 25, 25))

        total_deleted = 0
        if ids_to_delete:
            total_deleted = delete_news_by_ids(ids_to_delete)
            print(f"[trim] Per-day trim deleted {total_deleted} articles.")

        return total_deleted
    except Exception as e:
        print(f"Error trimming news: {e}")
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def save_question(q):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO questions (question) VALUES (%s)", (q,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_questions():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT question FROM questions")
            return [x[0] for x in c.fetchall()]
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

# ── RESULTS ───────────────────────────────────────────────────────────────────

def save_result(data):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO results (name, total, attempted, correct, wrong, accuracy, marks) VALUES (%s, %s, %s, %s, %s, %s, %s)", data)
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_results():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, name, total, attempted, correct, wrong, accuracy, marks FROM results")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_result(rowid):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM results WHERE id = %s", (rowid,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── SAVED ITEMS ───────────────────────────────────────────────────────────────

def save_item(item_type, content):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO saved_items (item_type, content) VALUES (%s, %s)", (item_type, content))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def get_saved_items():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, item_type, content, timestamp FROM saved_items ORDER BY timestamp DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_saved_item(item_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM saved_items WHERE id = %s", (item_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

def clean_old(days=15):
    conn = get_conn()
    if not conn: return
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with conn.cursor() as c:
            c.execute("DELETE FROM news WHERE date < %s", (cutoff,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── USER SETTINGS ─────────────────────────────────────────────────────────────

def get_retention(username):
    conn = get_conn()
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
        _safe_rollback(conn)
        return 15

def set_retention(username, days):
    conn = get_conn()
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
        _safe_rollback(conn)

# ── CA FILTERS ────────────────────────────────────────────────────────────────

def add_ca_filter(word):
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO ca_filters (word) VALUES (%s) ON CONFLICT (word) DO NOTHING", (word.lower().strip(),))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return False

def get_ca_filters():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, word FROM ca_filters ORDER BY word")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_ca_filter(filter_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ca_filters WHERE id = %s", (filter_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── AI REPORTS ────────────────────────────────────────────────────────────────

def save_ai_report(report_type, period_label, content):
    conn = get_conn()
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
        _safe_rollback(conn)
        return None

def get_ai_reports():
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, report_type, period_label, content, created_at FROM ai_reports ORDER BY created_at DESC")
            return c.fetchall()
    except Exception as e:
        print(e)
        _safe_rollback(conn)
        return []

def delete_ai_report(report_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ai_reports WHERE id = %s", (report_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── TEST PAPERS ───────────────────────────────────────────────────────────────

def save_test_paper(test_name, test_date, total_questions, attempted, not_attempted,
                    guessed_correct, guessed_incorrect, carelessness_notes):
    conn = get_conn()
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
        _safe_rollback(conn)
        return None

def get_test_papers():
    conn = get_conn()
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
        _safe_rollback(conn)
        return []

def delete_test_paper(paper_id):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM test_papers WHERE id = %s", (paper_id,))
        conn.commit()
    except Exception as e:
        print(e)
        _safe_rollback(conn)

# ── SYLLABUS SUMMARIES (Yojana, Kurukshetra, Economic Survey, Budget, Yearbook) ──

def save_syllabus_summary(resource_type, title, content, source_url=""):
    """Save a syllabus resource summary (Yojana, Kurukshetra, etc.)"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS syllabus_summaries (
                    id SERIAL PRIMARY KEY,
                    resource_type TEXT,
                    title TEXT,
                    content TEXT,
                    source_url TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                c.execute("ALTER TABLE syllabus_summaries ENABLE ROW LEVEL SECURITY")
            except Exception:
                pass
            c.execute(
                """
                INSERT INTO syllabus_summaries (resource_type, title, content, source_url)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (resource_type, title, content, source_url)
            )
            result_id = c.fetchone()[0]
        conn.commit()
        return result_id
    except Exception as e:
        print(f"Error saving syllabus summary: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def get_syllabus_summaries(resource_type=None):
    """Get syllabus summaries, optionally filtered by resource type"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            if resource_type:
                c.execute(
                    """
                    SELECT id, resource_type, title, content, source_url, saved_at
                    FROM syllabus_summaries
                    WHERE resource_type = %s
                    ORDER BY saved_at DESC
                    LIMIT 100
                    """,
                    (resource_type,)
                )
            else:
                c.execute(
                    """
                    SELECT id, resource_type, title, content, source_url, saved_at
                    FROM syllabus_summaries
                    ORDER BY saved_at DESC
                    LIMIT 200
                    """
                )
            return c.fetchall()
    except Exception as e:
        print(f"Error retrieving syllabus summaries: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

def delete_syllabus_summary(summary_id):
    """Delete a syllabus summary"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM syllabus_summaries WHERE id = %s", (summary_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting syllabus summary: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# SYLLABUS QUIZ FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

def save_syllabus_quiz(subject, questions_json, source="Article Summary"):
    """
    Save a quiz generated from an article summary
    Returns: quiz_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO syllabus_quizzes (subject, source, questions)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (subject, source, questions_json))
            
            quiz_id = c.fetchone()[0]
        conn.commit()
        return quiz_id
    except Exception as e:
        print(f"Error saving syllabus quiz: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_syllabus_quiz(quiz_id):
    """Get a specific quiz"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, resource_type, summary_id, questions, created_at
                FROM syllabus_quizzes WHERE id = %s
            """, (quiz_id,))
            
            result = c.fetchone()
            return result
    except Exception as e:
        print(f"Error fetching syllabus quiz: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def save_quiz_attempt(quiz_id, user_answers, score, percentage):
    """
    Save a quiz attempt/result
    Returns: attempt_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO syllabus_quiz_attempts (quiz_id, user_answers, score, percentage)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (quiz_id, user_answers, score, percentage))
            
            attempt_id = c.fetchone()[0]
        conn.commit()
        return attempt_id
    except Exception as e:
        print(f"Error saving quiz attempt: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_quiz_attempts(quiz_id, limit=10):
    """Get all attempts for a quiz"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, quiz_id, user_answers, score, percentage, attempted_at
                FROM syllabus_quiz_attempts
                WHERE quiz_id = %s
                ORDER BY attempted_at DESC
                LIMIT %s
            """, (quiz_id, limit))
            
            results = c.fetchall()
            return results
    except Exception as e:
        print(f"Error fetching quiz attempts: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_syllabus_quiz(quiz_id):
    """Delete a quiz and all its attempts"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            # Delete attempts first (due to foreign key)
            c.execute("DELETE FROM syllabus_quiz_attempts WHERE quiz_id = %s", (quiz_id,))
            # Delete quiz
            c.execute("DELETE FROM syllabus_quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting syllabus quiz: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# URL SUMMARY STORAGE
# ════════════════════════════════════════════════════════════════════════════

def save_url_summary(url, title, summary, subject=""):
    """
    Save a URL summary from the URL Summarizer tool
    Returns: summary_id
    """
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO url_summaries (url, title, subject, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET
                    title = EXCLUDED.title,
                    subject = EXCLUDED.subject,
                    summary = EXCLUDED.summary
                RETURNING id
            """, (url, title, subject, summary))
            
            summary_id = c.fetchone()[0]
        conn.commit()
        return summary_id
    except Exception as e:
        print(f"Error saving URL summary: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_url_summaries(limit=50):
    """Get all saved URL summaries"""
    conn = get_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT id, url, title, subject, summary, created_at
                FROM url_summaries
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            results = c.fetchall()
            return results
    except Exception as e:
        print(f"Error fetching URL summaries: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_url_summary(summary_id):
    """Delete a URL summary"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM url_summaries WHERE id = %s", (summary_id,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting URL summary: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# QUIZ STREAKS — track which days a user attempted a quiz
# ════════════════════════════════════════════════════════════════════════════

def _ensure_streak_table(conn):
    """Create quiz_streaks table if it doesn't exist."""
    try:
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS quiz_streaks (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    quiz_type TEXT NOT NULL DEFAULT 'CA Quiz',
                    quiz_date DATE NOT NULL,
                    score_pct REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(username, quiz_type, quiz_date)
                )
            """)
            try:
                c.execute("ALTER TABLE quiz_streaks ENABLE ROW LEVEL SECURITY")
            except Exception:
                pass
        conn.commit()
    except Exception as e:
        print(f"streak table ensure error: {e}")
        _safe_rollback(conn)


def save_quiz_streak(username, quiz_type, quiz_date, score_pct=0):
    """Record that the user took a quiz on a given date."""
    conn = get_connection()
    if not conn:
        return False
    try:
        _ensure_streak_table(conn)
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO quiz_streaks (username, quiz_type, quiz_date, score_pct)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username, quiz_type, quiz_date)
                DO UPDATE SET score_pct = GREATEST(quiz_streaks.score_pct, EXCLUDED.score_pct)
            """, (username, quiz_type, str(quiz_date), score_pct))
        conn.commit()
        return True
    except Exception as e:
        print(f"save_quiz_streak error: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_quiz_streaks(username, quiz_type=None, days=90):
    """
    Return list of (quiz_date, score_pct) rows for the given user
    within the last `days` days.
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        _ensure_streak_table(conn)
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        with conn.cursor() as c:
            if quiz_type:
                c.execute("""
                    SELECT quiz_date, score_pct FROM quiz_streaks
                    WHERE username = %s AND quiz_type = %s AND quiz_date >= %s
                    ORDER BY quiz_date DESC
                """, (username, quiz_type, cutoff))
            else:
                c.execute("""
                    SELECT quiz_date, score_pct FROM quiz_streaks
                    WHERE username = %s AND quiz_date >= %s
                    ORDER BY quiz_date DESC
                """, (username, cutoff))
            return c.fetchall()
    except Exception as e:
        print(f"get_quiz_streaks error: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_streak_dates_set(username, quiz_type=None, days=90):
    """Return a set of date strings (YYYY-MM-DD) for quick lookup."""
    rows = get_quiz_streaks(username, quiz_type, days)
    return {str(r[0]) for r in rows}


# ════════════════════════════════════════════════════════════════════════════
# NEWS BY DATE RANGE
# ════════════════════════════════════════════════════════════════════════════

def get_news_by_date_range(start_date, end_date):
    """
    Fetch news articles whose date falls in [start_date, end_date] (strings YYYY-MM-DD).
    Returns rows: (title, content, date, url, source, category)
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT title, content, date, url, source, category
                FROM news
                WHERE date >= %s AND date <= %s
                ORDER BY date DESC, id DESC
                LIMIT 500
            """, (str(start_date), str(end_date)))
            return c.fetchall()
    except Exception as e:
        print(f"get_news_by_date_range error: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_available_news_dates():
    """Return sorted list of distinct date strings (YYYY-MM-DD) available in the news table."""
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT DISTINCT date FROM news ORDER BY date DESC LIMIT 365")
            return [r[0] for r in c.fetchall()]
    except Exception as e:
        print(f"get_available_news_dates error: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


# ════════════════════════════════════════════════════════════════════════════
# AI-GENERATED CA QUIZZES (no DB data needed)
# ════════════════════════════════════════════════════════════════════════════

def _ensure_ai_ca_quiz_table(conn):
    try:
        with conn.cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS ai_ca_quizzes (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    range_label TEXT,
                    range_start TEXT,
                    range_end TEXT,
                    questions_json JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                c.execute("ALTER TABLE ai_ca_quizzes ENABLE ROW LEVEL SECURITY")
            except Exception:
                pass
        conn.commit()
    except Exception as e:
        print(f"ai_ca_quiz table ensure error: {e}")
        _safe_rollback(conn)


def save_ai_ca_quiz(username, range_label, range_start, range_end, questions_json):
    """Save an AI-generated CA quiz (for date ranges without DB data)."""
    conn = get_connection()
    if not conn:
        return None
    try:
        _ensure_ai_ca_quiz_table(conn)
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO ai_ca_quizzes (username, range_label, range_start, range_end, questions_json)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (username, range_label, str(range_start), str(range_end), questions_json))
            new_id = c.fetchone()[0]
        conn.commit()
        return new_id
    except Exception as e:
        print(f"save_ai_ca_quiz error: {e}")
        _safe_rollback(conn)
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_ai_ca_quizzes(username, limit=20):
    """Get AI-generated CA quizzes for a user."""
    conn = get_connection()
    if not conn:
        return []
    try:
        _ensure_ai_ca_quiz_table(conn)
        with conn.cursor() as c:
            c.execute("""
                SELECT id, username, range_label, range_start, range_end, questions_json, created_at
                FROM ai_ca_quizzes
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (username, limit))
            return c.fetchall()
    except Exception as e:
        print(f"get_ai_ca_quizzes error: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def delete_ai_ca_quiz(quiz_id):
    """Delete an AI-generated CA quiz."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM ai_ca_quizzes WHERE id = %s", (quiz_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"delete_ai_ca_quiz error: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

# ── SYSTEM CONFIG ─────────────────────────────────────────────────────────────

def set_config(key, value):
    """Set or update a system configuration value."""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO system_config (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE 
                SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
            """, (key, value))
        conn.commit()
    except Exception as e:
        print(f"Error setting config {key}: {e}")
        _safe_rollback(conn)
    finally:
        if conn:
            conn.close()

def get_config(key, default=None):
    """Retrieve a system configuration value."""
    conn = get_connection()
    if not conn:
        return default
    try:
        with conn.cursor() as c:
            c.execute("SELECT value FROM system_config WHERE key = %s", (key,))
            res = c.fetchone()
            if res:
                return res[0]
            return default
    except Exception as e:
        print(f"Error getting config {key}: {e}")
        return default
    finally:
        if conn:
            conn.close()

# ── USER AUTHENTICATION (DB-BACKED) ──────────────────────────────────────────

def _seed_default_users(connection):
    """Seed default users into the users table if it's empty (first run only)."""
    if not connection:
        return
    try:
        with connection.cursor() as c:
            c.execute("SELECT COUNT(*) FROM users")
            count = c.fetchone()[0]
            if count == 0:
                default_users = []
                try:
                    if "passwords" in st.secrets:
                        for username, password in st.secrets["passwords"].items():
                            role = "admin" if username == "admin" else "user"
                            default_users.append((username, str(password), role))
                except Exception:
                    pass
                
                for username, password, role in default_users:
                    c.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                        (username, password, role)
                    )
        connection.commit()
    except Exception as e:
        print(f"Error seeding default users: {e}")
        _safe_rollback(connection)


def get_credentials():
    """Load all active user credentials from the database as a dict {username: password}."""
    conn = get_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as c:
            c.execute("SELECT username, password FROM users WHERE is_active = TRUE")
            return {row[0]: row[1] for row in c.fetchall()}
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def validate_user(username, password):
    """Validate a username/password pair against the database and update last_login."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("SELECT password, is_active FROM users WHERE username = %s", (username,))
            row = c.fetchone()
            if row and row[0] == password and row[1]:
                # Update last login
                c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s", (username,))
                conn.commit()
                return True
            return False
    except Exception as e:
        print(f"Error validating user: {e}")
        return False
    finally:
        if conn:
            conn.close()


def user_exists(username):
    """Check if an active username exists in the database."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM users WHERE username = %s AND is_active = TRUE", (username,))
            return c.fetchone() is not None
    except Exception as e:
        print(f"Error checking user: {e}")
        return False
    finally:
        if conn:
            conn.close()

def is_admin(username):
    """Check if an active username is an admin."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("SELECT role FROM users WHERE username = %s AND is_active = TRUE", (username,))
            row = c.fetchone()
            return row is not None and row[0] == 'admin'
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_users():
    """Get a list of all users."""
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT username, role, is_active, has_news_access, last_login, created_at FROM users ORDER BY created_at DESC")
            return c.fetchall()
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []
    finally:
        if conn:
            conn.close()

def add_user(username, password, role):
    """Add a new user."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, password, role))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding user: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def update_user_password(username, new_password):
    """Update a user's password."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("UPDATE users SET password = %s WHERE username = %s", (new_password, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def toggle_user_active(username):
    """Toggle a user's active status."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("UPDATE users SET is_active = NOT is_active WHERE username = %s", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error toggling user status: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def delete_user(username):
    """Delete a user from the database."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("DELETE FROM users WHERE username = %s", (username,))
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

# ── NEWS ACCESS & MANAGEMENT ───────────────────────────────────────────────

def clear_all_news():
    """Clear all news from the database."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("TRUNCATE TABLE news")
        conn.commit()
        return True
    except Exception as e:
        print(f"Error clearing all news: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def set_news_access(username, granted):
    """Set news access for a user."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("UPDATE users SET has_news_access = %s WHERE username = %s", (granted, username))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error setting news access: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def has_news_access(username):
    """Check if a user has news access (admins always do)."""
    if is_admin(username):
        return True
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("SELECT has_news_access FROM users WHERE username = %s", (username,))
            row = c.fetchone()
            return row is not None and row[0]
    except Exception as e:
        print(f"Error checking news access: {e}")
        return False
    finally:
        if conn:
            conn.close()

def request_news_access(username):
    """Submit a request for news access."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO news_access_requests (username, status)
                VALUES (%s, 'pending')
                ON CONFLICT (username) DO UPDATE 
                SET status = 'pending', requested_at = CURRENT_TIMESTAMP
            """, (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error requesting news access: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()

def get_pending_access_requests():
    """Get all pending news access requests."""
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as c:
            c.execute("SELECT id, username, requested_at FROM news_access_requests WHERE status = 'pending' ORDER BY requested_at ASC")
            return c.fetchall()
    except Exception as e:
        print(f"Error getting pending access requests: {e}")
        return []
    finally:
        if conn:
            conn.close()

def resolve_access_request(username, approved):
    """Resolve a pending access request."""
    conn = get_connection()
    if not conn:
        return False
    try:
        status = 'approved' if approved else 'denied'
        with conn.cursor() as c:
            c.execute("""
                UPDATE news_access_requests 
                SET status = %s, reviewed_at = CURRENT_TIMESTAMP 
                WHERE username = %s
            """, (status, username))
            if approved:
                c.execute("UPDATE users SET has_news_access = TRUE WHERE username = %s", (username,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error resolving access request: {e}")
        _safe_rollback(conn)
        return False
    finally:
        if conn:
            conn.close()
