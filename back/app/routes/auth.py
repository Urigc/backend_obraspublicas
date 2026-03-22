
from flask import Blueprint, request
from app.database import get_db
from app.helpers import ok, bad_request, db_error_response
import hashlib

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _hash_password(raw: str) -> str:
    """
    Hash SHA-256 simple.
    Para producción real usa bcrypt o argon2.
    Asegúrate de guardar contraseñas hasheadas al insertar usuarios.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------------------------------------------
#  POST /api/auth/login
# ----------------------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Valida las credenciales contra la tabla `usuario`.

    Body JSON esperado:
        { "username": "dir_obras", "password": "admin123", "role": "director" }

    Respuesta exitosa:
        { "success": true, "data": { "role", "id", "nombre", "username" } }

    ── SQL que debes colocar en tu BD ──────────────────────────
    La tabla `usuario` que necesitas tener:

        CREATE TABLE usuario (
            id          VARCHAR(20)  PRIMARY KEY,
            username    VARCHAR(50)  UNIQUE NOT NULL,
            password    VARCHAR(255) NOT NULL,   -- SHA-256 hash
            nombre      VARCHAR(100) NOT NULL,
            rol         VARCHAR(20)  NOT NULL     -- 'director','supervisor','proyectista','secretaria'
        );

    Ejemplo de INSERT de usuarios iniciales:
        INSERT INTO usuario (id, username, password, nombre, rol) VALUES
          ('D001',   'dir_obras', '<hash de admin123>',  'Ing. Director',    'director'),
          ('S001',   'sup_001',   '<hash de super123>',  'Uriel González',   'supervisor'),
          ('P001',   'pro_001',   '<hash de proy123>',   'Arq. Proyectista', 'proyectista'),
          ('SEC001', 'sec_001',   '<hash de sec123>',    'Secretaría Admin', 'secretaria');
    ─────────────────────────────────────────────────────────────
    """
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role     = (body.get("role") or "").strip().lower()

    if not username or not password or not role:
        return bad_request("Proporciona username, password y role.")

    try:
        with get_db() as (conn, cur):
            # ── AQUÍ VA TU QUERY de autenticación ──────────────────────
            cur.execute("""
                SELECT id, username, nombre, rol
                FROM usuario
                WHERE username = %s
                  AND password = %s
                  AND rol = %s
            """, (username, _hash_password(password), role))
            # ────────────────────────────────────────────────────────────

            row = cur.fetchone()

        if not row:
            return bad_request("Usuario o contraseña incorrectos.")

        return ok({
            "id":       row["id"],
            "username": row["username"],
            "nombre":   row["nombre"],
            "role":     row["rol"],
        }, "Inicio de sesión exitoso.")

    except Exception as exc:
        return db_error_response(exc)


# ----------------------------------------------------------------
#  POST /api/auth/logout  (stateless — solo confirma al cliente)
# ----------------------------------------------------------------
@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    El estado de sesión vive en el sessionStorage del navegador.
    Este endpoint simplemente confirma que puede limpiar el estado.
    """
    return ok(message="Sesión cerrada.")
