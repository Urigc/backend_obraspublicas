from conexion import get_conn
from etl_dimensiones import cargar_todas
from etl_hechos import cargar_hechos

def ejecutar():
    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("═══ ETL Dirección de Obras Públicas ═══")
        cargar_todas(cur)
        cargar_hechos(cur)
        conn.commit()
        print("═══ ETL completado sin errores ═══")
    except Exception as e:
        conn.rollback()
        print(f"✗ Error — rollback aplicado: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    ejecutar()