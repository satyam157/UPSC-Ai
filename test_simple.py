#!/usr/bin/env python3
"""Simple test with just a few items"""

import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def test_simple():
    print("Testing simple insert...", flush=True)
    
    # Connect
    try:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            conn = psycopg2.connect(db_url)
        else:
            conn = psycopg2.connect(
                dbname=os.getenv("PG_DB", "postgres"),
                user=os.getenv("PG_USER", "postgres"),
                password=os.getenv("PG_PASSWORD", "postgres"),
                host=os.getenv("PG_HOST", "localhost"),
                port=os.getenv("PG_PORT", "5432")
            )
    except Exception as e:
        print(f"Connection failed: {e}", flush=True)
        return
    
    print("Connected", flush=True)
    
    # Count before
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM news")
            before = c.fetchone()[0]
            print(f"Before: {before} items", flush=True)
    except Exception as e:
        print(f"Count error: {e}", flush=True)
        conn.close()
        return
    
    # Insert one item
    print("Inserting one test item...", flush=True)
    try:
        with conn.cursor() as c:
            c.execute(
                """
                INSERT INTO news (title, content, date)
                VALUES (%s, %s, %s)
                ON CONFLICT (title) DO NOTHING
                """,
                ("TEST" + str(datetime.now().timestamp()), "test content", "2026-04-11")
            )
        conn.commit()
        print("Commit successful", flush=True)
    except Exception as e:
        print(f"Insert error: {e}", flush=True)
        conn.rollback()
    
    # Count after
    try:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM news")
            after = c.fetchone()[0]
            print(f"After: {after} items", flush=True)
            print(f"Added: {after - before} items", flush=True)
    except Exception as e:
        print(f"Count error: {e}", flush=True)
    
    conn.close()
    print("Done", flush=True)

if __name__ == "__main__":
    test_simple()
