import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'inventory_system'),
    'port': int(os.environ.get('DB_PORT', 5432))
}


def get_db_connection():
    """Return a psycopg2 connection using RealDictCursor by default."""
    database_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    if database_url:
        return psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


@contextmanager
def db_cursor(commit: bool = False):
    """Context manager yielding a cursor (RealDictCursor). Closes connection automatically."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()
