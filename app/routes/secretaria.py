# app/routes/secretaria.py
# ================================================================
#  MÓDULO: SECRETARÍA
#
#  ┌─────────────────────────────────────────────────────────────┐
#  │  ARCHIVO FRONT RELACIONADO: secretaria/secretaria.js        │
#  └─────────────────────────────────────────────────────────────┘
#
#  Endpoints:
#    PERMISOS
#      GET    /api/permisos           → renderPermisosList()
#      POST   /api/permisos           → submitPermiso()
#      DELETE /api/permisos/<id>      → deletePermiso(id)
#
#    ACTAS DE ENTREGA
#      GET    /api/actas              → renderActasList()
#      POST   /api/actas              → submitActa()
#      GET    /api/actas/<id>         → detalle con firmantes
#      DELETE /api/actas/<id>         → deleteActa(id)
# ================================================================

from flask import Blueprint, request
from app.database import get_db
from app.helpers import ok, created, bad_request, not_found, db_error_response, require_fields
from app.middleware.auth import require_auth
import time

secretaria_bp = Blueprint("secretaria", __name__)

# Firmantes reglamentarios (deben existir en toda acta)
FIRMANTE_ROLES = [
    "delegado",
    "constructora",
    "presidente",
    "director",
    "contralor",
]


# ================================================================
#  PERMISOS
# ================================================================

# ── GET /api/permisos ────────────────────────────────────────────
@secretaria_bp.route("/api/permisos", methods=["GET"])
@require_auth("secretaria", "director", "supervisor")
def get_permisos(current_user):
    """
    Lista todos los oficios de permisos registrados.
    FRONT: secretaria.js → renderPermisosList()
    Reemplaza: getData('op_permisos')

    Parámetros de query opcionales:
      ?obra=<id>          → filtra por obra
      ?instancia=CFE      → filtra por instancia emisora

    ── SQL de tu tabla permiso ─────────────────────────────────
        CREATE TABLE permiso (
            id          VARCHAR(20)   PRIMARY KEY,
            id_obra     VARCHAR(30)   REFERENCES obra(id),
            instancia   VARCHAR(100)  NOT NULL,
            num_oficio  VARCHAR(100)  NOT NULL,
            descripcion TEXT,
            fecha       DATE,
            creado_por  VARCHAR(20)   REFERENCES usuario(id),
            creado_en   TIMESTAMPTZ   DEFAULT NOW()
        );
    ─────────────────────────────────────────────────────────────
    """
    obra_filter      = request.args.get("obra")
    instancia_filter = request.args.get("instancia")

    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU QUERY de permisos ───────────────────────────
            cur.execute("""
                SELECT
                    p.id,
                    p.id_obra       AS "obraId",
                    o.nombre        AS "obraNombre",
                    p.instancia,
                    p.num_oficio    AS "oficio",
                    p.descripcion   AS "desc",
                    p.fecha,
                    p.creado_en     AS "creadoEn"
                FROM permiso p
                JOIN obra o ON o.id = p.id_obra
                WHERE (%s IS NULL OR p.id_obra = %s)
                  AND (%s IS NULL OR p.instancia ILIKE %s)
                ORDER BY p.creado_en DESC
            """, (
                obra_filter, obra_filter,
                instancia_filter, f"%{instancia_filter}%" if instancia_filter else None,
            ))
            # ──────────────────────────────────────────────────────────
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/permisos ───────────────────────────────────────────
@secretaria_bp.route("/api/permisos", methods=["POST"])
@require_auth("secretaria")
def create_permiso(current_user):
    """
    Registra un oficio de permiso.
    FRONT: secretaria.js → submitPermiso()
    Reemplaza:
        const permisos = getData('op_permisos');
        permisos.push({...});
        setData('op_permisos', permisos);

    Body JSON:
    {
      "obraId":    "OBR-EXP-2026-001",
      "instancia": "CFE",
      "oficio":    "Oficio CFE-2025-001",
      "desc":      "Autorización para cruce de líneas eléctricas",
      "fecha":     "2025-11-15"
    }
    """
    body = request.get_json(silent=True) or {}
    valid, err = require_fields(body, "obraId", "instancia", "oficio")
    if not valid:
        return err

    permiso_id = f"PRM-{int(time.time())}"

    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU INSERT de permiso ───────────────────────────
            cur.execute("""
                INSERT INTO permiso (id, id_obra, instancia, num_oficio, descripcion, fecha, creado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                permiso_id,
                body["obraId"],
                body["instancia"],
                body["oficio"],
                body.get("desc") or None,
                body.get("fecha") or None,
                current_user["id"],
            ))
            # ──────────────────────────────────────────────────────────
        return created({"id": permiso_id}, f"Permiso {permiso_id} registrado.")
    except Exception as exc:
        return db_error_response(exc)


# ── DELETE /api/permisos/<id> ────────────────────────────────────
@secretaria_bp.route("/api/permisos/<permiso_id>", methods=["DELETE"])
@require_auth("secretaria", "director")
def delete_permiso(permiso_id, current_user):
    """
    Elimina un oficio de permiso.
    FRONT: secretaria.js → deletePermiso(id)
    """
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU DELETE de permiso ───────────────────────────
            cur.execute("DELETE FROM permiso WHERE id = %s RETURNING id", (permiso_id,))
            # ──────────────────────────────────────────────────────────
            if not cur.fetchone():
                return not_found("Permiso no encontrado.")
        return ok(message="Permiso eliminado.")
    except Exception as exc:
        return db_error_response(exc)


# ================================================================
#  ACTAS DE ENTREGA
# ================================================================

# ── GET /api/actas ───────────────────────────────────────────────
@secretaria_bp.route("/api/actas", methods=["GET"])
@require_auth("secretaria", "director", "supervisor")
def get_actas(current_user):
    """
    Lista todas las actas de entrega con sus firmantes.
    FRONT: secretaria.js → renderActasList()
    Reemplaza: getData('op_actas')

    ── SQL de tus tablas ────────────────────────────────────────
        CREATE TABLE acta_entrega (
            id          VARCHAR(20)  PRIMARY KEY,
            id_obra     VARCHAR(30)  UNIQUE REFERENCES obra(id),
            num_acta    VARCHAR(30),
            fecha       DATE         NOT NULL,
            observaciones TEXT,
            creado_por  VARCHAR(20)  REFERENCES usuario(id),
            creado_en   TIMESTAMPTZ  DEFAULT NOW()
        );

        CREATE TABLE firmante (
            id          SERIAL       PRIMARY KEY,
            id_acta     VARCHAR(20)  REFERENCES acta_entrega(id) ON DELETE CASCADE,
            cargo       VARCHAR(50)  NOT NULL,   -- delegado/constructora/presidente/director/contralor
            nombre      VARCHAR(100) NOT NULL,
            apellido_p  VARCHAR(100),
            apellido_m  VARCHAR(100)
        );
    ─────────────────────────────────────────────────────────────
    """
    obra_filter = request.args.get("obra")
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU QUERY de actas ──────────────────────────────
            cur.execute("""
                SELECT
                    a.id,
                    a.id_obra       AS "obraId",
                    o.nombre        AS "obraNombre",
                    a.num_acta      AS "numActa",
                    a.fecha,
                    a.observaciones AS "obs",
                    a.creado_en     AS "creadoEn",
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'cargo',     f.cargo,
                                'nombre',    f.nombre,
                                'apellidoP', f.apellido_p,
                                'apellidoM', f.apellido_m
                            )
                        ) FILTER (WHERE f.id IS NOT NULL),
                        '[]'
                    ) AS firmantes
                FROM acta_entrega a
                JOIN obra o ON o.id = a.id_obra
                LEFT JOIN firmante f ON f.id_acta = a.id
                WHERE (%s IS NULL OR a.id_obra = %s)
                GROUP BY a.id, o.nombre
                ORDER BY a.creado_en DESC
            """, (obra_filter, obra_filter))
            # ──────────────────────────────────────────────────────────
            rows = [dict(r) for r in cur.fetchall()]
        return ok(rows)
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/actas ──────────────────────────────────────────────
@secretaria_bp.route("/api/actas", methods=["POST"])
@require_auth("secretaria")
def create_acta(current_user):
    """
    Registra un Acta de Entrega con sus 5 firmantes.
    FRONT: secretaria.js → submitActa()
    Reemplaza:
        actas.push({id, obraId, obraNombre, fecha, obs, firmantes, ...});
        setData('op_actas', actas);

    Body JSON:
    {
      "obraId":  "OBR-EXP-2026-001",
      "numActa": "ACT-2026-001",
      "fecha":   "2026-12-20",
      "obs":     "Obra entregada sin observaciones",
      "firmantes": [
        { "cargo": "delegado",     "nombre": "Juan",    "apellidoP": "García",  "apellidoM": "López" },
        { "cargo": "constructora", "nombre": "Roberto", "apellidoP": "Sánchez", "apellidoM": "Pérez" },
        { "cargo": "presidente",   "nombre": "Miguel",  "apellidoP": "Torres",  "apellidoM": "Cruz" },
        { "cargo": "director",     "nombre": "Carlos",  "apellidoP": "Ruiz",    "apellidoM": "Medina" },
        { "cargo": "contralor",    "nombre": "Ana",     "apellidoP": "Flores",  "apellidoM": "Vargas" }
      ]
    }
    """
    body = request.get_json(silent=True) or {}
    valid, err = require_fields(body, "obraId", "fecha")
    if not valid:
        return err

    firmantes = body.get("firmantes", [])
    # Validar que al menos 3 firmantes tengan nombre y apellido
    completos = [f for f in firmantes if f.get("nombre") and f.get("apellidoP")]
    if len(completos) < 3:
        return bad_request("Se requieren al menos 3 firmantes completos (nombre y apellido paterno).")

    acta_id  = body.get("numActa") or f"ACT-{int(time.time())}"

    try:
        with get_db() as (conn, cur):

            # ── AQUÍ VA TU INSERT de acta_entrega ──────────────────────
            cur.execute("""
                INSERT INTO acta_entrega (id, id_obra, num_acta, fecha, observaciones, creado_por)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                acta_id,
                body["obraId"],
                acta_id,
                body["fecha"],
                body.get("obs") or None,
                current_user["id"],
            ))
            # ──────────────────────────────────────────────────────────

            # ── AQUÍ VAN TUS INSERTs de firmantes ──────────────────────
            for f in firmantes:
                if f.get("nombre"):   # sólo insertar si tiene nombre
                    cur.execute("""
                        INSERT INTO firmante (id_acta, cargo, nombre, apellido_p, apellido_m)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        acta_id,
                        f.get("cargo", ""),
                        f["nombre"],
                        f.get("apellidoP") or None,
                        f.get("apellidoM") or None,
                    ))
            # ──────────────────────────────────────────────────────────

            # Marcar la obra como finalizada
            cur.execute(
                "UPDATE obra SET status = 'finalizada' WHERE id = %s",
                (body["obraId"],)
            )

        return created({"id": acta_id}, f"Acta {acta_id} registrada exitosamente.")

    except Exception as exc:
        return db_error_response(exc)


# ── GET /api/actas/<id> ──────────────────────────────────────────
@secretaria_bp.route("/api/actas/<acta_id>", methods=["GET"])
@require_auth("secretaria", "director")
def get_acta(acta_id, current_user):
    """Detalle completo de un acta con todos sus firmantes."""
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU QUERY de acta individual ────────────────────
            cur.execute("""
                SELECT a.*, o.nombre AS "obraNombre"
                FROM acta_entrega a
                JOIN obra o ON o.id = a.id_obra
                WHERE a.id = %s
            """, (acta_id,))
            acta = cur.fetchone()
            if not acta:
                return not_found("Acta no encontrada.")

            cur.execute("""
                SELECT cargo, nombre, apellido_p AS "apellidoP", apellido_m AS "apellidoM"
                FROM firmante
                WHERE id_acta = %s
                ORDER BY id
            """, (acta_id,))
            firmantes = [dict(f) for f in cur.fetchall()]
            # ──────────────────────────────────────────────────────────

        result = dict(acta)
        result["firmantes"] = firmantes
        return ok(result)
    except Exception as exc:
        return db_error_response(exc)


# ── DELETE /api/actas/<id> ───────────────────────────────────────
@secretaria_bp.route("/api/actas/<acta_id>", methods=["DELETE"])
@require_auth("secretaria", "director")
def delete_acta(acta_id, current_user):
    """
    Elimina un acta (y sus firmantes por CASCADE).
    FRONT: secretaria.js → deleteActa(id)
    """
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU DELETE de acta ──────────────────────────────
            cur.execute("DELETE FROM acta_entrega WHERE id = %s RETURNING id", (acta_id,))
            # ──────────────────────────────────────────────────────────
            if not cur.fetchone():
                return not_found("Acta no encontrada.")
        return ok(message="Acta eliminada.")
    except Exception as exc:
        return db_error_response(exc)
