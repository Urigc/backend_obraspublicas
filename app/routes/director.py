
from flask import Blueprint, request
from app.database import get_db
from app.helpers import ok, created, bad_request, not_found, db_error_response, require_fields
from app.middleware.auth import require_auth

director_bp = Blueprint("director", __name__)

# ── GET /api/obras ───────────────────────────────────────────────
@director_bp.route("/api/obras", methods=["GET"])
@require_auth("director", "supervisor", "proyectista", "secretaria")
def get_obras(current_user):
    supervisor_filter = request.args.get("supervisor")
    status_filter     = request.args.get("status")
    search            = request.args.get("q", "").strip()
    

    try:
        
        with get_db() as (conn, cur):
        
            cur.execute("""
    INSERT INTO public.obra (
        id_obra, codigo_expediente, nombre_obra, etapa,
        fecha_inicio, fecha_final, descripcion, beneficiarios,
        id_constructora, id_region, codigo_supervisor, status
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    obra_id[:20],
    body["expediente"][:15],   # ← CHAR(15)
    body["nombre"][:200],
    body.get("etapa", 1),
    body.get("fechaInicio"),
    body.get("fechaFin"),
    body.get("descripcion", "")[:500],
    body.get("beneficiarios", "")[:500],
    body.get("constructoraId", "")[:10],  # ← CHAR(10)
    body.get("regionId", "")[:5],         # ← CHAR(5)
    body.get("supervisorId", "")[:20],    # ← CHAR(20)
    "activa"
))
            obras = [dict(row) for row in cur.fetchall()]

        return ok(obras)

    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/obras
@director_bp.route("/api/obras", methods=["POST"])
@require_auth("director")
def create_obra(current_user):

    body = request.get_json(silent=True) or {}
    return jsonify({"debug": True, "body_recibido": body}), 200
    

    valid, err = require_fields(body, "expediente", "nombre", "region")
    if not valid:
        return err

    obra_id = f"OBR-{body['expediente']}"[:20].strip()

    try:
        with get_db() as (conn, cur):
            # 1. INSERT en public.obra (Datos Maestros)
            cur.execute("""
                INSERT INTO public.obra (
                    id_obra, codigo_expediente, nombre_obra, etapa,
                    fecha_inicio, fecha_final, descripcion, beneficiarios,
                    id_constructora, id_region, codigo_supervisor, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'activa')
            """, (
                obra_id,
                body["expediente"],
                body["nombre"],
                body.get("etapa", 1),
                body.get("fechaInicio"),
                body.get("fechaFin"),
                body.get("descripcion", ""),
                body.get("beneficiarios", ""),
                body["constructoraId"],
                body.get("region", "")[:5],
                body["supervisorId"]
            ))

            presupuesto_id = f"PRE-{body['expediente']}"[:10].strip()
            cur.execute("""
                INSERT INTO public.presupuesto_obra (
                    id_presupuesto, presupuesto_total, id_proyectista, id_obra
                ) VALUES (%s, %s, %s, %s)
            """, (
                presupuesto_id,
                body.get("presupuesto", 0),
                body.get("proyectistaId", "P001"), # Valor por defecto o del body
                obra_id
            ))

            # 3. INSERT en public.financia (Relación M:N con fuentes)
            fuentes = body.get("fuentes", [])
            for fuente_id in fuentes:
                cur.execute("""
                    INSERT INTO public.financia (id_obra, id_fuente)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (obra_id, fuente_id))

        return created({"id": obra_id}, f"Obra '{body['nombre']}' vinculada exitosamente en el sistema.")

    except Exception as exc:
        return db_error_response(exc)


# ── DELETE /api/obras/<id> ───────────────────────────────────────
@director_bp.route("/api/obras/<obra_id>", methods=["DELETE"])
@require_auth("director")
def delete_obra(obra_id, current_user):
    try:
        obra_id_clean = obra_id.strip()

        with get_db() as (conn, cur):
            # ── QUERY AJUSTADO A TU COLUMNA id_obra ───────────────────
            cur.execute("""
                DELETE FROM public.obra 
                WHERE id_obra = %s 
                RETURNING id_obra
            """, (obra_id_clean,))
            # ──────────────────────────────────────────────────────────
            
            row = cur.fetchone()
            if not row:
                return not_found(f"La obra con ID '{obra_id_clean}' no existe en la base de datos.")

        return ok(message=f"Obra '{obra_id_clean}' eliminada correctamente junto con sus dependencias.")

    except Exception as exc:
        return db_error_response(exc)



# ── GET /api/constructoras ───────────────────────────────────────
@director_bp.route("/api/constructoras", methods=["GET"])
@require_auth("director", "supervisor", "proyectista", "secretaria")
def get_constructoras(current_user):

    try:
        with get_db() as (conn, cur):
            cur.execute("""
                SELECT 
                    id_constructora AS "id", 
                    nombre_const AS "nombre", 
                    rfc, 
                    tipo_ejecutor AS "tipo"
                FROM public.constructora
                ORDER BY nombre_const ASC
            """)
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/constructoras ──────────────────────────────────────
@director_bp.route("/api/constructoras", methods=["POST"])
@require_auth("director")
def create_constructora(current_user):
    body = request.get_json(silent=True) or {}
    
    valid, err = require_fields(body, "id", "nombre", "tipo")
    if not valid:
        return err

    constr_id = f"CONSTR-{body['rfc']}"
    try:
        with get_db() as (conn, cur):
            cur.execute("""
                INSERT INTO public.constructora (
                    id_constructora, 
                    rfc, 
                    nombre_const, 
                    tipo_ejecutor
                ) VALUES (%s, %s, %s, %s)
                RETURNING id_constructora
            """, (
                body["id"].strip(),
                body.get("rfc", "").strip(), # Opcional según tu SQL
                body["nombre"].strip(),
                body["tipo"].strip()
            ))
            # ──────────────────────────────────────────────────────────
        return created({"id": body["id"]}, f"Constructora '{body['nombre']}' registrada con éxito.")
    except Exception as exc:
        return db_error_response(exc)


# ================================================================
#  CONCURSO DE SELECCIÓN
# ================================================================

# ── GET /api/concursos ───────────────────────────────────────────
@director_bp.route("/api/concursos", methods=["GET"])
@require_auth("director", "supervisor")
def get_concursos(current_user):
  
    obra_filter = request.args.get("obra")
    try:
        with get_db() as (conn, cur):
            cur.execute("""
                SELECT
                    s.id_participante AS "id",
                    s.id_obra AS "obraId",
                    o.nombre_obra AS "obraNombre",
                    s.constructora,
                    s.aprobado,
                    s.razones_decision AS "razones"
                FROM public.opcion_seleccion s
                JOIN public.obra o ON o.id_obra = s.id_obra
                WHERE (%s IS NULL OR s.id_obra = %s)
                ORDER BY s.id_participante DESC
            """, (obra_filter, obra_filter))
            # ──────────────────────────────────────────────────────────
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/concursos ──────────────────────────────────────────
@director_bp.route("/api/concursos", methods=["POST"])
@require_auth("director")
def create_concurso(current_user):
  
    body = request.get_json(silent=True) or {}
    valid, err = require_fields(body, "obraId", "constructora", "razones")
    if not valid:
        return err

    import time
    part_id = f"P-{int(time.time()) % 100000}"

    try:
        with get_db() as (conn, cur):
            cur.execute("""
                INSERT INTO public.opcion_seleccion (
                    id_participante, id_obra, constructora, aprobado, razones_decision
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id_participante
            """, (
                part_id,
                body["obraId"],
                body["constructora"],
                # Convertimos a boolean real para Postgres
                body.get("resultado") == "aprobada", 
                body["razones"],
            ))
        return created({"id": part_id}, "Propuesta de concurso registrada en Neon.")
    except Exception as exc:
        return db_error_response(exc)


# ================================================================
#  FUENTES PRESUPUESTARIAS
# ================================================================

# ── GET /api/fuentes ─
@director_bp.route("/api/fuentes", methods=["GET"])
@require_auth("director", "supervisor", "proyectista", "secretaria")
def get_fuentes(current_user):

    try:
        with get_db() as (conn, cur):
            cur.execute("""
                SELECT 
                    id_fuente AS "id", 
                    grado_nivel AS "nivel", 
                    programa
                FROM public.fuente_presupuestaria
                ORDER BY grado_nivel, programa
            """)
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)
    



# ── POST /api/obras/<id>/fuentes ─────────────────────────────────
@director_bp.route("/api/obras/<obra_id>/fuentes", methods=["POST"])
@require_auth("director")
def add_fuente_to_obra(obra_id, current_user):
    body = request.get_json(silent=True) or {}
    fuente_id = body.get("fuenteId")
    
    if not fuente_id:
        return bad_request("Falta fuenteId.")

    try:
        with get_db() as (conn, cur):
            cur.execute("""
                INSERT INTO public.financia (id_obra, id_fuente)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (obra_id.strip(), fuente_id.strip()))
            # ──────────────────────────────────────────────────────────
        return created(message="Fuente vinculada financieramente a la obra.")
    except Exception as exc:
        return db_error_response(exc)
