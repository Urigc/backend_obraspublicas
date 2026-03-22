
from flask import Blueprint, request
from app.database import get_db
from app.helpers import ok, created, bad_request, not_found, db_error_response, require_fields
from app.middleware.auth import require_auth
import time

supervisor_bp = Blueprint("supervisor", __name__)


# ── GET /api/informes ──
@supervisor_bp.route("/api/informes", methods=["GET"])
@require_auth("director", "supervisor")
def get_informes(current_user):
    obra_filter = request.args.get("obra")
    anio_filter = request.args.get("anio")

    supervisor_id = current_user["id"] if current_user["role"] == "supervisor" else None

    try:
        with get_db() as (conn, cur):
            cur.execute("""
                SELECT
                    i.id_informe AS "id",
                    i.id_obra AS "obraId",
                    o.codigo_expediente AS "obraExpediente",
                    o.nombre_obra AS "obraNombre",
                    i.codigo_supervisor AS "supervisorId",
                    p.nombre || ' ' || p.apellido_paterno AS "supervisorNombre",
                    i.ano_infor AS "anio",
                    i.mes,
                    i.porcentaje_avance_fisico AS "avanceFisico",
                    i.porcentaje_avance_presupuestario AS "avanceFinanciero",
                    i.descripcion,
                    i.doc_infome AS "documento"
                FROM public.informes i
                JOIN public.obra o ON o.id_obra = i.id_obra
                JOIN public.personal p ON p.codigo_personal = i.codigo_supervisor
                WHERE (%s IS NULL OR i.codigo_supervisor = %s)
                  AND (%s IS NULL OR i.id_obra = %s)
                  AND (%s IS NULL OR i.ano_infor = %s::int)
                ORDER BY i.ano_infor DESC, i.mes ASC
            """, (
                supervisor_id, supervisor_id,
                obra_filter, obra_filter,
                anio_filter, anio_filter,
            ))
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/informes ───
@supervisor_bp.route("/api/informes", methods=["POST"])
@require_auth("supervisor")
def create_informe(current_user):
    body = request.get_json(silent=True) or {}
    
    valid, err = require_fields(body, "obraId", "anio", "mes", "avanceFisico", "avanceFinanciero")
    if not valid:
        return err

    informe_id = f"INF-{int(time.time()) % 1000000}"

    try:
        with get_db() as (conn, cur):
            # Verificar que la obra esté asignada a este supervisor en public.obra
            cur.execute(
                "SELECT id_obra FROM public.obra WHERE id_obra = %s AND codigo_supervisor = %s",
                (body["obraId"], current_user["id"])
            )
            if not cur.fetchone():
                return bad_request("No tienes permiso para reportar en esta obra.")

            cur.execute("""
                INSERT INTO public.informes (
                    id_informe, ano_infor, mes, 
                    porcentaje_avance_fisico, 
                    porcentaje_avance_presupuestario, 
                    doc_infome, descripcion, 
                    id_obra, codigo_supervisor
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id_informe
            """, (
                informe_id,
                int(body["anio"]),
                body["mes"], # Tu SQL dice character(30), puede ser "Marzo" o "03"
                int(body["avanceFisico"]),
                int(body["avanceFinanciero"]),
                body.get("documento", ""), 
                body.get("descripcion", ""),
                body["obraId"],
                current_user["id"]
            ))

        return created({"id": informe_id}, "Informe mensual guardado en Neon.")

    except Exception as exc:
        return db_error_response(exc)


# ── GET /api/informes/<id> ───────
@supervisor_bp.route("/api/informes/<informe_id>", methods=["GET"])
@require_auth("director", "supervisor")
def get_informe(informe_id, current_user):
    try:
        with get_db() as (conn, cur):
            cur.execute("""
                SELECT
                    i.id_informe AS "id",
                    i.id_obra AS "obraId",
                    o.nombre_obra AS "obraNombre",
                    i.codigo_supervisor AS "supervisorId",
                    p.nombre || ' ' || p.apellido_paterno AS "supervisorNombre",
                    i.ano_infor AS "anio",
                    i.mes,
                    i.porcentaje_avance_fisico AS "avanceFisico",
                    i.porcentaje_avance_presupuestario AS "avanceFinanciero",
                    i.descripcion,
                    i.doc_infome AS "documento"
                FROM public.informes i
                JOIN public.obra o ON o.id_obra = i.id_obra
                JOIN public.personal p ON p.codigo_personal = i.codigo_supervisor
                WHERE i.id_informe = %s
            """, (informe_id.strip(),))
            # ──────────────────────────────────────────────────────────
            
            row = cur.fetchone()

        if not row:
            return not_found(f"Informe '{informe_id}' no encontrado en el sistema.")

        return ok(dict(row))

    except Exception as exc:
        return db_error_response(exc)


# ── DELETE /api/informes/<id> ────────────────────────────────────
@supervisor_bp.route("/api/informes/<informe_id>", methods=["DELETE"])
@require_auth("supervisor", "director")
def delete_informe(informe_id, current_user):
    try:
        with get_db() as (conn, cur):
            # Si es supervisor, solo puede borrar los suyos
            if current_user["role"] == "supervisor":
                cur.execute(
                    "SELECT id_informe FROM public.informes WHERE id_informe = %s AND codigo_supervisor = %s",
                    (informe_id, current_user["id"])
                )
                if not cur.fetchone():
                    return bad_request("Acceso denegado a este informe.")

            cur.execute("DELETE FROM public.informes WHERE id_informe = %s RETURNING id_informe", (informe_id,))
            if not cur.fetchone():
                return not_found("El informe no existe.")

        return ok(message="Informe eliminado de la base de datos.")
    except Exception as exc:
        return db_error_response(exc)
