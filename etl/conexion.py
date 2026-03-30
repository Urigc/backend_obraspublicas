import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "Obras_Publicas"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
