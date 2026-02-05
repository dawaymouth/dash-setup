"""
Database connection module for Redshift.
"""
import os
from contextlib import contextmanager
from typing import Generator, Any
import redshift_connector
from dotenv import load_dotenv

load_dotenv()


def get_connection_params() -> dict[str, Any]:
    """Get Redshift connection parameters from environment variables."""
    return {
        "host": os.getenv("REDSHIFT_HOST", "localhost"),
        "port": int(os.getenv("REDSHIFT_PORT", "5439")),
        "database": os.getenv("REDSHIFT_DATABASE", "dev"),
        "user": os.getenv("REDSHIFT_USER", ""),
        "password": os.getenv("REDSHIFT_PASSWORD", ""),
    }


@contextmanager
def get_db_connection() -> Generator[redshift_connector.Connection, None, None]:
    """Context manager for database connections."""
    conn = None
    try:
        conn = redshift_connector.connect(**get_connection_params())
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor() -> Generator[redshift_connector.Cursor, None, None]:
    """Context manager for database cursors."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


def execute_query(query: str, params: tuple = None) -> list[dict]:
    """Execute a query and return results as a list of dictionaries."""
    with get_db_cursor() as cursor:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        columns = [desc[0] for desc in cursor.description]
        results = cursor.fetchall()
        
        return [dict(zip(columns, row)) for row in results]
