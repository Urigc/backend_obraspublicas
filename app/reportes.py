from flask import Blueprint
from app.helpers import ok, server_error
from app.conexion import get_conn 

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.route('/api/v1/dwh/gasto-fuente', methods=['GET'])
def get_gasto_fuente():
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM dwh.v_gasto_por_fuente")
        
        columns = [desc[0] for desc in cur.description]
        data = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        cur.close()
        return ok(data=data, message="Datos para BI cargados correctamente")
        
    except Exception as e:
        print(f"❌ Error en reporte DWH: {e}")
        return server_error("Error al consultar el Warehouse")
    finally:
        if conn:
            conn.close()