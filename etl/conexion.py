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


if not load_dotenv():
    print("⚠️ ¡Cuidado! No se encontró el archivo .env")

def conectar_db():
    password = os.getenv('DB_PASS')
    
    if not password:
        print("❌ Error: La contraseña no se leyó del archivo .env")
        return None

    try:
        conexion = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=password, # Aquí es donde fallaba
            port=os.getenv('DB_PORT')
        )
        return conexion
    except psycopg2.OperationalError as e:
        print(f"❌ Error de conexión: {e}")
        return None