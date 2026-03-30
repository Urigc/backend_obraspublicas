import psycopg2.extras
from conexion import get_conn

def cargar_dim_tiempo(cur):
    """
    Genera filas de tiempo a partir de los años/meses
    presentes en informes y en las fechas de obra.
    """
    cur.execute("""
        SELECT DISTINCT
            ano_infor            AS anio,
            TRIM(mes)            AS nombre_mes
        FROM public.informes
        UNION
        SELECT DISTINCT
            EXTRACT(YEAR FROM fecha_inicio)::INT,
            TO_CHAR(fecha_inicio, 'TMMonth')
        FROM public.obra
    """)
    filas = cur.fetchall()

    meses_num = {
        'enero':1,'febrero':2,'marzo':3,'abril':4,
        'mayo':5,'junio':6,'julio':7,'agosto':8,
        'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12
    }

    for anio, nombre_mes in filas:
        nombre_lower = nombre_mes.lower().strip()
        mes_num = meses_num.get(nombre_lower, 0)
        if mes_num == 0:
            continue
        trimestre = (mes_num - 1) // 3 + 1

        cur.execute("""
            INSERT INTO dwh.dim_tiempo (anio, trimestre, mes, nombre_mes)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (anio, mes) DO NOTHING
        """, (anio, trimestre, mes_num, nombre_mes.capitalize()))

    print("  ✓ dim_tiempo cargada")


def cargar_dim_obra(cur):
    cur.execute("""
        SELECT
            TRIM(id_obra)              AS id_obra,
            TRIM(codigo_expediente)    AS codigo_expediente,
            TRIM(nombre_obra)          AS nombre_obra,
            etapa,
            EXTRACT(YEAR FROM fecha_inicio)::INT  AS anio_inicio,
            EXTRACT(YEAR FROM fecha_final)::INT   AS anio_fin,
            CASE
                WHEN fecha_final < CURRENT_DATE THEN 'TERMINADA'
                ELSE 'EN_EJECUCION'
            END AS estatus
        FROM public.obra
    """)
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO dwh.dim_obra
                (id_obra_oltp, codigo_expediente, nombre_obra,
                 etapa, anio_inicio, anio_fin, estatus)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id_obra_oltp) DO UPDATE SET
                estatus = EXCLUDED.estatus,
                anio_fin = EXCLUDED.anio_fin
        """, row)

    print("  ✓ dim_obra cargada")


def cargar_dim_constructora(cur):
    cur.execute("""
        SELECT
            TRIM(c.id_constructora),
            TRIM(c.nombre_const),
            TRIM(c.tipo_ejecutor),
            COUNT(o.id_participante)                        AS veces_participante,
            COUNT(o.id_participante) FILTER (WHERE o.aprobado) AS veces_aprobada
        FROM public.constructora c
        LEFT JOIN public.opcion_seleccion o
            ON TRIM(o.constructora) = TRIM(c.nombre_const)
        GROUP BY c.id_constructora, c.nombre_const, c.tipo_ejecutor
    """)
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO dwh.dim_constructora
                (id_constructora_oltp, nombre_const, tipo_ejecutor,
                 veces_participante, veces_aprobada)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (id_constructora_oltp) DO UPDATE SET
                veces_participante = EXCLUDED.veces_participante,
                veces_aprobada     = EXCLUDED.veces_aprobada
        """, row)

    print("  ✓ dim_constructora cargada")


def cargar_dim_supervisor(cur):
    # JOIN de supervisor + personal para obtener nombre completo
    cur.execute("""
        SELECT
            TRIM(s.codigo_personal),
            TRIM(p.nombre) || ' ' ||
            TRIM(p.apellido_paterno) || ' ' ||
            COALESCE(TRIM(p.apellido_materno), '') AS nombre_completo,
            s.telefono
        FROM public.supervisor s
        JOIN public.personal p
            ON TRIM(s.codigo_personal) = TRIM(p.codigo_personal)
    """)
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO dwh.dim_supervisor
                (codigo_oltp, nombre_completo, telefono)
            VALUES (%s,%s,%s)
            ON CONFLICT (codigo_oltp) DO UPDATE SET
                nombre_completo = EXCLUDED.nombre_completo
        """, row)

    print("  ✓ dim_supervisor cargada")


def cargar_dim_fuente(cur):
    cur.execute("""
        SELECT
            TRIM(id_fuente),
            TRIM(grado_nivel),
            programa
        FROM public.fuente_presupuestaria
    """)
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO dwh.dim_fuente
                (id_fuente_oltp, grado_nivel, programa)
            VALUES (%s,%s,%s)
            ON CONFLICT (id_fuente_oltp) DO NOTHING
        """, row)

    print("  ✓ dim_fuente cargada")


def cargar_dim_region(cur):
    cur.execute("""
        SELECT
            TRIM(id_region),
            TRIM(comunidad),
            TRIM(barrio),
            colonia
        FROM public.region
    """)
    for row in cur.fetchall():
        cur.execute("""
            INSERT INTO dwh.dim_region
                (id_region_oltp, comunidad, barrio, colonia)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (id_region_oltp) DO NOTHING
        """, row)

    print("  ✓ dim_region cargada")


def cargar_todas(cur):
    print("→ Cargando dimensiones...")
    cargar_dim_tiempo(cur)
    cargar_dim_obra(cur)
    cargar_dim_constructora(cur)
    cargar_dim_supervisor(cur)
    cargar_dim_fuente(cur)
    cargar_dim_region(cur)