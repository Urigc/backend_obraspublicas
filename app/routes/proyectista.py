# app/routes/proyectista.py
# ================================================================
#  MÓDULO: PROYECTISTA
#
#  ┌─────────────────────────────────────────────────────────────┐
#  │  ARCHIVO FRONT RELACIONADO: proyectista/proyectista.js      │
#  └─────────────────────────────────────────────────────────────┘
#
#  Endpoints:
#    GET    /api/presupuestos/<obra_id>           → renderEditor() / renderResumen()
#    POST   /api/presupuestos                     → crea cabecera del presupuesto
#    PUT    /api/presupuestos/<obra_id>            → actualiza cabecera
#
#    Costos (filas del editor tipo spreadsheet):
#    GET    /api/presupuestos/<obra_id>/costos     → renderCostoRows()
#    POST   /api/presupuestos/<obra_id>/costos     → addCostoRow()
#    PUT    /api/presupuestos/<obra_id>/costos/<n> → updateRow()
#    DELETE /api/presupuestos/<obra_id>/costos/<n> → deleteRow()
#
#  NOTAS DE INTEGRACIÓN:
#    proyectista.js usa presupuestoData (objeto en memoria) y guarda
#    todo en localStorage con savePresupuesto().
#    Al integrar, cada llamada al backend reemplaza una de esas
#    funciones. Ver los comentarios inline para el mapeo exacto.
# ================================================================

from flask import Blueprint, request
from app.database import get_db
from app.helpers import ok, created, bad_request, not_found, db_error_response, require_fields
from app.middleware.auth import require_auth

proyectista_bp = Blueprint("proyectista", __name__)

# Categorías válidas (deben coincidir con el front)
VALID_CATS = {"materiales", "mano_obra", "equipo", "indirectos", "imprevistos"}


# ── GET /api/presupuestos/<obra_id> ──────────────────────────────
@proyectista_bp.route("/api/presupuestos/<obra_id>", methods=["GET"])
@require_auth("proyectista", "director", "supervisor")
def get_presupuesto(obra_id, current_user):
    """
    Obtiene la cabecera + todos los costos de un presupuesto.
    Estructura de respuesta:
    {
      "id": "PRES-OBR-001",
      "obraId": "OBR-EXP-2026-001",
      "proyectistaId": "P001",
      "costos": {
        "materiales":  [ {id, desc, unit, qty, price}, ... ],
        "mano_obra":   [ ... ],
        "equipo":      [ ... ],
        "indirectos":  [ ... ],
        "imprevistos": [ ... ]
      },
      "totalGeneral": 450000.00
    }

    FRONT: proyectista.js → selectObra(id) → carga presupuestoData
    Reemplaza:
        const presupuestos = getPresupuestos();
        presupuestoData = presupuestos[id] || { materiales:[], ... };

    ── SQL de tus tablas ────────────────────────────────────────
        CREATE TABLE presupuesto (
            id              VARCHAR(30) PRIMARY KEY,
            id_obra         VARCHAR(30) UNIQUE REFERENCES obra(id),
            id_proyectista  VARCHAR(20) REFERENCES usuario(id),
            fecha_creacion  TIMESTAMPTZ DEFAULT NOW(),
            fecha_actualizacion TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE costo (
            id          SERIAL       PRIMARY KEY,
            id_presupuesto VARCHAR(30) REFERENCES presupuesto(id) ON DELETE CASCADE,
            categoria   VARCHAR(20)  NOT NULL,  -- materiales/mano_obra/equipo/indirectos/imprevistos
            descripcion VARCHAR(300) NOT NULL,
            unidad      VARCHAR(30)  DEFAULT 'pza',
            cantidad    NUMERIC(12,3) DEFAULT 0,
            precio_unitario NUMERIC(12,2) DEFAULT 0,
            orden       INT          DEFAULT 0
        );
    ─────────────────────────────────────────────────────────────
    """
    try:
        with get_db() as (conn, cur):

            # ── AQUÍ VA TU QUERY de cabecera de presupuesto ────────────
            cur.execute("""
                SELECT id, id_obra AS "obraId", id_proyectista AS "proyectistaId",
                       fecha_creacion AS "fechaCreacion"
                FROM presupuesto
                WHERE id_obra = %s
            """, (obra_id,))
            # ──────────────────────────────────────────────────────────
            pres = cur.fetchone()

            if not pres:
                # No existe presupuesto aún para esta obra → devolvemos estructura vacía
                return ok({
                    "id": None,
                    "obraId": obra_id,
                    "costos": {cat: [] for cat in VALID_CATS},
                    "totalGeneral": 0
                })

            pres = dict(pres)

            # ── AQUÍ VA TU QUERY de costos ─────────────────────────────
            cur.execute("""
                SELECT id, categoria, descripcion AS "desc",
                       unidad AS "unit",
                       cantidad AS "qty",
                       precio_unitario AS "price",
                       orden
                FROM costo
                WHERE id_presupuesto = %s
                ORDER BY categoria, orden, id
            """, (pres["id"],))
            # ──────────────────────────────────────────────────────────
            all_costos = cur.fetchall()

        # Agrupar costos por categoría (idéntico a presupuestoData del front)
        costos = {cat: [] for cat in VALID_CATS}
        total = 0.0
        for c in all_costos:
            cd = dict(c)
            cat = cd.pop("categoria")
            if cat in costos:
                costos[cat].append(cd)
                total += float(cd.get("qty", 0)) * float(cd.get("price", 0))

        pres["costos"] = costos
        pres["totalGeneral"] = round(total, 2)
        return ok(pres)

    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/presupuestos ───────────────────────────────────────
@proyectista_bp.route("/api/presupuestos", methods=["POST"])
@require_auth("proyectista")
def create_presupuesto(current_user):
    """
    Crea la cabecera del presupuesto para una obra.
    Se llama una sola vez; después se usan los endpoints de costos.

    FRONT: proyectista.js → selectObra(id) si no existe presupuesto aún.
    Body JSON: { "obraId": "OBR-EXP-2026-001" }
    """
    body = request.get_json(silent=True) or {}
    valid, err = require_fields(body, "obraId")
    if not valid:
        return err

    pres_id = f"PRES-{body['obraId']}"

    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU INSERT de presupuesto ───────────────────────
            cur.execute("""
                INSERT INTO presupuesto (id, id_obra, id_proyectista)
                VALUES (%s, %s, %s)
                ON CONFLICT (id_obra) DO NOTHING
                RETURNING id
            """, (pres_id, body["obraId"], current_user["id"]))
            # ──────────────────────────────────────────────────────────
        return created({"id": pres_id}, "Presupuesto creado.")
    except Exception as exc:
        return db_error_response(exc)


# ── POST /api/presupuestos/<obra_id>/costos ──────────────────────
@proyectista_bp.route("/api/presupuestos/<obra_id>/costos", methods=["POST"])
@require_auth("proyectista")
def add_costo(obra_id, current_user):
    """
    Agrega una fila (concepto) al presupuesto.
    FRONT: proyectista.js → addCostoRow()
    Reemplaza:
        presupuestoData[currentCat].push({ desc, unit, qty, price });

    Body JSON:
    {
      "categoria": "materiales",
      "desc":      "Cemento Portland gris 50kg",
      "unit":      "saco",
      "qty":       200,
      "price":     185.00
    }
    """
    body = request.get_json(silent=True) or {}
    valid, err = require_fields(body, "categoria", "desc")
    if not valid:
        return err

    if body["categoria"] not in VALID_CATS:
        return bad_request(f"Categoría inválida. Usa: {', '.join(VALID_CATS)}")

    try:
        with get_db() as (conn, cur):

            # Obtener el id del presupuesto para esta obra
            cur.execute(
                "SELECT id FROM presupuesto WHERE id_obra = %s",
                (obra_id,)
            )
            pres = cur.fetchone()
            if not pres:
                return not_found("Presupuesto no encontrado para esta obra. Créalo primero.")

            # Calcular el siguiente número de orden dentro de la categoría
            cur.execute("""
                SELECT COALESCE(MAX(orden), 0) + 1
                FROM costo
                WHERE id_presupuesto = %s AND categoria = %s
            """, (pres["id"], body["categoria"]))
            orden = cur.fetchone()[0]

            # ── AQUÍ VA TU INSERT de costo ─────────────────────────────
            cur.execute("""
                INSERT INTO costo (
                    id_presupuesto, categoria, descripcion,
                    unidad, cantidad, precio_unitario, orden
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                pres["id"],
                body["categoria"],
                body["desc"],
                body.get("unit", "pza"),
                float(body.get("qty", 0)),
                float(body.get("price", 0)),
                orden,
            ))
            # ──────────────────────────────────────────────────────────
            new_id = cur.fetchone()["id"]

        return created({"id": new_id}, "Concepto de costo agregado.")
    except Exception as exc:
        return db_error_response(exc)


# ── PUT /api/presupuestos/<obra_id>/costos/<costo_id> ────────────
@proyectista_bp.route("/api/presupuestos/<obra_id>/costos/<int:costo_id>", methods=["PUT"])
@require_auth("proyectista")
def update_costo(obra_id, costo_id, current_user):
    """
    Actualiza una fila existente (edición inline en el editor).
    FRONT: proyectista.js → updateRow(index, field, value)
    Cualquiera de los campos se puede enviar parcialmente.

    Body JSON (parcial):
    { "desc": "Nuevo nombre", "qty": 250, "price": 190.00 }
    """
    body = request.get_json(silent=True) or {}
    if not body:
        return bad_request("No se enviaron campos para actualizar.")

    allowed = {"desc": "descripcion", "unit": "unidad",
               "qty": "cantidad", "price": "precio_unitario"}
    set_parts = []
    values    = []
    for front_key, db_col in allowed.items():
        if front_key in body:
            set_parts.append(f"{db_col} = %s")
            values.append(body[front_key])

    if not set_parts:
        return bad_request("Ningún campo válido enviado.")

    values.append(costo_id)

    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU UPDATE de costo ─────────────────────────────
            cur.execute(
                f"UPDATE costo SET {', '.join(set_parts)} WHERE id = %s RETURNING id",
                values
            )
            # ──────────────────────────────────────────────────────────
            if not cur.fetchone():
                return not_found("Concepto no encontrado.")

        return ok(message="Concepto actualizado.")
    except Exception as exc:
        return db_error_response(exc)


# ── DELETE /api/presupuestos/<obra_id>/costos/<costo_id> ─────────
@proyectista_bp.route("/api/presupuestos/<obra_id>/costos/<int:costo_id>", methods=["DELETE"])
@require_auth("proyectista")
def delete_costo(obra_id, costo_id, current_user):
    """
    Elimina una fila del editor de costos.
    FRONT: proyectista.js → deleteRow(index)
    """
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU DELETE de costo ─────────────────────────────
            cur.execute("DELETE FROM costo WHERE id = %s RETURNING id", (costo_id,))
            # ──────────────────────────────────────────────────────────
            if not cur.fetchone():
                return not_found("Concepto no encontrado.")

        return ok(message="Concepto eliminado.")
    except Exception as exc:
        return db_error_response(exc)


# ── GET /api/presupuestos/<obra_id>/resumen ──────────────────────
@proyectista_bp.route("/api/presupuestos/<obra_id>/resumen", methods=["GET"])
@require_auth("proyectista", "director", "supervisor")
def get_resumen(obra_id, current_user):
    """
    Devuelve los totales por categoría para la vista de Resumen General.
    FRONT: proyectista.js → renderResumen()

    Respuesta:
    {
      "obraNombre": "...",
      "presupuestoAsignado": 850000,
      "categorias": [
        { "nombre": "materiales", "subtotal": 320000, "pct": 71.1, "items": 12 },
        ...
      ],
      "totalElaborado": 450000
    }
    """
    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU QUERY de resumen por categoría ──────────────
            cur.execute("""
                SELECT
                    o.nombre            AS "obraNombre",
                    o.presupuesto_total AS "presupuestoAsignado",
                    c.categoria,
                    COUNT(c.id)                                    AS items,
                    COALESCE(SUM(c.cantidad * c.precio_unitario), 0) AS subtotal
                FROM obra o
                LEFT JOIN presupuesto p ON p.id_obra = o.id
                LEFT JOIN costo c       ON c.id_presupuesto = p.id
                WHERE o.id = %s
                GROUP BY o.nombre, o.presupuesto_total, c.categoria
            """, (obra_id,))
            # ──────────────────────────────────────────────────────────
            rows = cur.fetchall()

        if not rows:
            return not_found("Obra no encontrada.")

        obra_nombre  = rows[0]["obraNombre"]
        pres_asignado = float(rows[0]["presupuestoAsignado"] or 0)
        total = sum(float(r["subtotal"]) for r in rows if r["categoria"])

        categorias = []
        for r in rows:
            if r["categoria"]:
                sub = float(r["subtotal"])
                categorias.append({
                    "nombre":   r["categoria"],
                    "subtotal": round(sub, 2),
                    "pct":      round((sub / total * 100) if total else 0, 1),
                    "items":    r["items"],
                })

        return ok({
            "obraNombre":          obra_nombre,
            "presupuestoAsignado": pres_asignado,
            "categorias":          categorias,
            "totalElaborado":      round(total, 2),
        })

    except Exception as exc:
        return db_error_response(exc)
