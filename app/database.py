import os
import psycopg2
import psycopg2.extras   
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Detecta si existe DATABASE_URL (para Neon/Render) 
    o si usa los parámetros por separado (Local).
    """
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Esto es lo que usará Render/Neon
        return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "Direccion_Obras_Publicas"),
            user=os.getenv("urigc"),
            password=os.getenv("123456"),
            cursor_factory=psycopg2.extras.RealDictCursor
        )

@contextmanager
def get_db():
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        yield conn, cur
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        raise exc
    finally:
        if conn:
            conn.close()


def test_connection() -> bool:
    """
    Prueba de conectividad. Llámala al arrancar la app.
    Retorna True si la conexión funciona, False si no.
    """
    try:
        with get_db() as (conn, cur):
            cur.execute("SELECT 1;")
        return True
    except Exception as e:
        print(f"[DB] Error de conexión: {e}")
        return False
