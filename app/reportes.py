import os
from flask import Blueprint, request, abort
from .helpers import ok, server_error
from .database import get_conn

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/api/v1/dwh/gasto-fuente', methods=['GET'])
def get_gasto_fuente():
    # 1. Seguridad
    api_key = request.headers.get('X-API-KEY')
    expected_key = os.getenv("REPORTING_KEY", "clave_temporal_123")
    
    if api_key != expected_key:
        abort(401, description="No autorizado")

    # 2. Ejecución
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM dwh.v_gasto_por_fuente")
        
        columns = [desc[0] for desc in cur.description]
        data = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        cur.close()
        return ok(data=data, message="Datos obtenidos exitosamente")
        
    except Exception as e:
        print(f"❌ Error DWH: {e}")
        return server_error("Error al consultar el almacén de datos")
        
    finally:
        if conn:
            conn.close()
