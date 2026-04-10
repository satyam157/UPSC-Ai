#!/usr/bin/env python3
"""Simple direct database test without using db.py functions"""

import psycopg2
import feedparser
from datetime import datetime
from filter import is_relevant
import os
from dotenv import load_dotenv

load_dotenv()

def get_fresh_connection():
    """Get a fresh PostgreSQL connection"""
    try:
        # Try from environment variables
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return psycopg2.connect(db_url)
        
        # Try standard connection
        conn = psycopg2.connect(
            dbname=os.getenv("PG_DB", "postgres"),
            user=os.getenv("PG_USER", "postgres"),
            password=os.getenv("PG_PASSWORD", "postgres"),
            host=os.getenv("PG_HOST", "localhost"),
            port=os.getenv("PG_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def test_direct():
    print("=" * 80)
    print("DIRECT DATABASE TEST (No db.py functions)")
    print("=" * 80)
    
    # Test 1: Connection
    print("\n1️⃣ Testing connection...")
    conn = get_fresh_connection()
    if not conn:
        print("✗ FAILED to connect")
        return
    print("✓ Connected")
    
    # Test 2: List tables
    print("\n2️⃣ Checking existing tables...")
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_SCHEMA='public'
            """)
            tables = c.fetchall()
            print(f"   Tables: {[t[0] for t in tables]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Check news table structure
    print("\n3️⃣ Checking 'news' table structure...")
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT column_name, data_type 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME='news'
            """)
            cols = c.fetchall()
            if cols:
                for col_name, col_type in cols:
                    print(f"   - {col_name}: {col_type}")
            else:
                print("   ✗ 'news' table doesn't exist!")
    except Exception as e:
        print(f"   Error checking schema: {e}")
    conn.close()
    
    # Test 4: Count existing news
    print("\n4️⃣ Counting existing news items...")
    conn = get_fresh_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM news")
            count = c.fetchone()[0]
            print(f"   Total items in DB: {count}")
    except Exception as e:
        print(f"   Error: {e}")
    conn.close()
    
    # Test 5: Fetch news from feeds
    print("\n5️⃣ Fetching news from feeds...")
    news_list = []
    urls = [
        "https://www.thehindu.com/news/national/feeder/default.rss",
    ]
    
    for url in urls:
        feed = feedparser.parse(url)
        for e in feed.entries[:3]:  # Just 3 items
            title = e.get("title", "").strip()
            if title and len(title) > 30 and is_relevant(title):
                news_list.append({
                    "title": title,
                    "content": getattr(e, "summary", "").strip()[:200],
                    "date": datetime.now().strftime("%Y-%m-%d")
                })
                print(f"   ✓ {title[:60]}")
    
    if not news_list:
        print("   ✗ No news found!")
        return
    
    # Test 6: Insert news
    print(f"\n6️⃣ Inserting {len(news_list)} news items...")
    conn = get_fresh_connection()
    try:
        with conn.cursor() as c:
            inserted = 0
            for n in news_list:
                try:
                    # Try WITHOUT url column (since it doesn't exist)
                    c.execute(
                        """
                        INSERT INTO news (title, content, date)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (title) DO NOTHING
                        """,
                        (n["title"], n["content"], n["date"])
                    )
                    if c.rowcount > 0:
                        inserted += 1
                        print(f"   ✓ Inserted: {n['title'][:50]}")
                except Exception as e:
                    print(f"   ✗ Error: {e}")
        
        conn.commit()
        print(f"\n   Total inserted: {inserted}")
    except Exception as e:
        print(f"   Commit error: {e}")
    finally:
        conn.close()
    
    # Test 7: Verify count increased
    print("\n7️⃣ Verifying insertion...")
    conn = get_fresh_connection()
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM news")
            new_count = c.fetchone()[0]
            print(f"   Total items now: {new_count}")
    except Exception as e:
        print(f"   Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_direct()
