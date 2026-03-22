
from functools import wraps
from flask import request
from app.helpers import bad_request

# Roles válidos del sistema
VALID_ROLES = {"director", "supervisor", "proyectista", "secretaria"}


def get_current_user():
    """
    Extrae la identidad del usuario desde los headers HTTP.
    El frontend los envía automáticamente en cada fetch().
    """
    return {
        "role":     request.headers.get("X-User-Role", "").lower(),
        "id":       request.headers.get("X-User-Id", ""),
        "nombre":   request.headers.get("X-User-Nombre", ""),
        "username": request.headers.get("X-User-Username", ""),
    }


def require_auth(*allowed_roles):
    """
    Decorador que protege un endpoint.
    Uso:
        @require_auth("director")
        @require_auth("director", "supervisor")   ← múltiples roles

    Si el usuario no tiene el rol correcto → 401/403.
    Si pasa, inyecta current_user como primer argumento de la función.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()

            if not user["role"] or user["role"] not in VALID_ROLES:
                return bad_request("Autenticación requerida. Headers X-User-Role / X-User-Id ausentes."), 401

            if allowed_roles and user["role"] not in allowed_roles:
                return bad_request(
                    f"Acceso denegado. Rol '{user['role']}' no puede ejecutar esta acción."
                ), 403

            if not user["id"]:
                return bad_request("Header X-User-Id requerido."), 401

            # Inyecta el usuario resuelto como kwarg
            return fn(*args, current_user=user, **kwargs)
        return wrapper
    return decorator
