import os
import psycopg2
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app) # Esto permite que tu GitHub Pages lea los datos

def get_db_connection():
    # Usamos la variable de entorno que configuraremos en Render
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    return conn

@app.route('/')
def index():
    return "API de Obras Públicas operando correctamente."

@app.route('/api/proyectos', methods=['GET'])
def get_proyectos():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Aquí pon una de tus 15 tablas, por ejemplo 'proyectos'
        cur.execute('SELECT * FROM proyectos;') 
        columnas = [desc[0] for desc in cur.description]
        resultados = [dict(zip(columnas, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(resultados)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))