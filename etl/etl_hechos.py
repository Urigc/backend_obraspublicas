from conexion import get_conn

def cargar_hechos(cur):
    print("→ Cargando tabla de hechos...")

    # Recupera todos los informes con sus datos de obra y fuente
    cur.execute("""
        SELECT
            -- IDs para lookup en dimensiones
            TRIM(i.id_obra)              AS id_obra,
            TRIM(i.codigo_supervisor)    AS cod_supervisor,
            i.ano_infor                  AS anio,
            TRIM(i.mes)                  AS nombre_mes,
            i.porcentaje_avance_fisico,
            i.porcentaje_avance_presupuestario,

            -- Datos de obra para joins
            TRIM(o.id_constructora)      AS id_constructora,
            TRIM(o.id_region)            AS id_region,
            o.fecha_inicio,

            -- Presupuesto total
            po.presupuesto_total,

            -- Costos agregados por categoría (pivot manual)
            COALESCE(SUM(c.costo) FILTER (
                WHERE TRIM(c.categoria) ILIKE '%material%'), 0)    AS costo_materiales,
            COALESCE(SUM(c.costo) FILTER (
                WHERE TRIM(c.categoria) ILIKE '%mano%'), 0)        AS costo_mano_obra,
            COALESCE(SUM(c.costo) FILTER (
                WHERE TRIM(c.categoria) ILIKE '%equipo%'), 0)      AS costo_equipo,
            COALESCE(SUM(c.costo) FILTER (
                WHERE TRIM(c.categoria) ILIKE '%indirect%'), 0)    AS costo_indirectos,
            COALESCE(SUM(c.costo) FILTER (
                WHERE TRIM(c.categoria) NOT ILIKE '%material%'
                  AND TRIM(c.categoria) NOT ILIKE '%mano%'
                  AND TRIM(c.categoria) NOT ILIKE '%equipo%'
                  AND TRIM(c.categoria) NOT ILIKE '%indirect%'), 0) AS costo_otros,
            COALESCE(SUM(c.costo), 0)                              AS costo_total,

            -- Número de informes acumulados hasta ese mes
            COUNT(i2.id_informe) AS num_informes_acum,

            -- Número de permisos de la obra
            COUNT(DISTINCT p.id_oficio) AS num_permisos,

            -- Fuentes de financiamiento (puede haber varias por obra)
            TRIM(f.id_fuente) AS id_fuente

        FROM public.informes i
        JOIN public.obra o
            ON TRIM(i.id_obra) = TRIM(o.id_obra)
        LEFT JOIN public.presupuesto_obra po
            ON TRIM(po.id_obra) = TRIM(o.id_obra)
        LEFT JOIN public.costos c
            ON TRIM(c.id_presupuesto) = TRIM(po.id_presupuesto)
        LEFT JOIN public.informes i2
            ON TRIM(i2.id_obra) = TRIM(i.id_obra)
           AND (i2.ano_infor < i.ano_infor
                OR (i2.ano_infor = i.ano_infor
                    AND i2.id_informe <= i.id_informe))
        LEFT JOIN public.permisos p
            ON TRIM(p.id_obra) = TRIM(i.id_obra)
        JOIN public.financia f
            ON TRIM(f.id_obra) = TRIM(i.id_obra)
        GROUP BY
            i.id_obra, i.codigo_supervisor, i.ano_infor, i.mes,
            i.porcentaje_avance_fisico, i.porcentaje_avance_presupuestario,
            o.id_constructora, o.id_region, o.fecha_inicio,
            po.presupuesto_total, f.id_fuente, i.id_informe
    """)

    filas = cur.fetchall()
    meses_num = {
        'enero':1,'febrero':2,'marzo':3,'abril':4,
        'mayo':5,'junio':6,'julio':7,'agosto':8,
        'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12
    }

    insertados = 0
    for fila in filas:
        (id_obra, cod_sup, anio, nombre_mes,
         av_fisico, av_financiero,
         id_const, id_region, fecha_inicio,
         presup_total,
         c_mat, c_mano, c_equipo, c_indir, c_otros, c_total,
         num_inf, num_perm, id_fuente) = fila

        mes_num = meses_num.get(nombre_mes.lower().strip(), 0)
        if mes_num == 0:
            continue

        # Días de ejecución hasta ese mes
        dias = (anio - fecha_inicio.year) * 365 + (mes_num - fecha_inicio.month) * 30

        # Flag de irregularidad: avance físico muy por encima del financiero
        flag = bool(av_financiero > 0 and av_fisico > av_financiero + 30)

        # Lookup de IDs en dimensiones
        cur.execute("SELECT id_tiempo FROM dwh.dim_tiempo WHERE anio=%s AND mes=%s",
                    (anio, mes_num))
        row = cur.fetchone()
        if not row:
            continue
        id_tiempo = row[0]

        cur.execute("SELECT id_dim_obra FROM dwh.dim_obra WHERE id_obra_oltp=%s",
                    (id_obra,))
        row = cur.fetchone()
        if not row:
            continue
        id_dim_obra = row[0]

        cur.execute("SELECT id_dim_constructora FROM dwh.dim_constructora WHERE id_constructora_oltp=%s",
                    (id_const,))
        row = cur.fetchone()
        if not row:
            continue
        id_dim_const = row[0]

        cur.execute("SELECT id_dim_supervisor FROM dwh.dim_supervisor WHERE codigo_oltp=%s",
                    (cod_sup,))
        row = cur.fetchone()
        if not row:
            continue
        id_dim_sup = row[0]

        cur.execute("SELECT id_dim_fuente FROM dwh.dim_fuente WHERE id_fuente_oltp=%s",
                    (id_fuente,))
        row = cur.fetchone()
        if not row:
            continue
        id_dim_fuente = row[0]

        cur.execute("SELECT id_dim_region FROM dwh.dim_region WHERE id_region_oltp=%s",
                    (id_region,))
        row = cur.fetchone()
        if not row:
            continue
        id_dim_region = row[0]

        cur.execute("""
            INSERT INTO dwh.fact_gasto_obra (
                id_tiempo, id_dim_obra, id_dim_constructora,
                id_dim_supervisor, id_dim_fuente, id_dim_region,
                presupuesto_total,
                costo_materiales, costo_mano_obra, costo_equipo,
                costo_indirectos, costo_otros, costo_total_registrado,
                avance_fisico_pct, avance_financiero_pct,
                num_informes_acum, num_permisos,
                dias_ejecucion, irregularidad_flag
            ) VALUES (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s
            )
        """, (
            id_tiempo, id_dim_obra, id_dim_const,
            id_dim_sup, id_dim_fuente, id_dim_region,
            presup_total,
            c_mat, c_mano, c_equipo, c_indir, c_otros, c_total,
            av_fisico, av_financiero,
            num_inf, num_perm,
            dias, flag
        ))
        insertados += 1

    print(f"  ✓ fact_gasto_obra: {insertados} filas insertadas") 