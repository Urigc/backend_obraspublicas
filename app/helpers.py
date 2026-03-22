

from flask import jsonify
import psycopg2


# ---- Respuestas estándar ----------------------------------------

def ok(data=None, message: str = "OK", status: int = 200):
    """
    Respuesta exitosa.
    El frontend espera: { success: true, data: {...} }
    """
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def created(data=None, message: str = "Creado exitosamente"):
    return ok(data, message, 201)


def bad_request(message: str = "Petición inválida"):
    return jsonify({"success": False, "message": message}), 400


def not_found(message: str = "Recurso no encontrado"):
    return jsonify({"success": False, "message": message}), 404


def server_error(message: str = "Error interno del servidor"):
    return jsonify({"success": False, "message": message}), 500


# ---- Guard de campos requeridos --------------------------------

def require_fields(body: dict, *fields):
    """
    Valida que los campos estén presentes y no vacíos.
    Devuelve (True, None) si todo OK,
    o (False, response) con el error 400 listo para retornar.
    """
    missing = [f for f in fields if not body.get(f)]
    if missing:
        return False, bad_request(f"Campos requeridos faltantes: {', '.join(missing)}")
    return True, None


# ---- Manejo de errores psycopg2 --------------------------------

def db_error_response(exc: Exception):
    """
    Convierte excepciones de psycopg2 en respuestas HTTP legibles.
    Evita exponer detalles internos al cliente en producción.
    """
    if isinstance(exc, psycopg2.errors.UniqueViolation):
        return jsonify({
            "success": False,
            "message": "Ya existe un registro con ese identificador único."
        }), 409

    if isinstance(exc, psycopg2.errors.ForeignKeyViolation):
        return jsonify({
            "success": False,
            "message": "El registro referenciado no existe (violación de llave foránea)."
        }), 409

    if isinstance(exc, psycopg2.errors.NotNullViolation):
        return jsonify({
            "success": False,
            "message": "Un campo obligatorio llegó vacío a la base de datos."
        }), 400

    # Error genérico — no exponemos el traceback al cliente
    print(f"[DB ERROR] {type(exc).__name__}: {exc}")
    return server_error("Error inesperado en la base de datos.")
