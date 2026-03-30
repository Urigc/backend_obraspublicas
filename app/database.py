import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def get_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("❌ No se encontró DATABASE_URL en el .env")
    return psycopg2.connect(url)
