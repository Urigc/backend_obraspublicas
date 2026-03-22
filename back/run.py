import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    print(f"\n🏗️  Sistema de Obras Públicas — API iniciando en puerto {port}")
    print(f"   Entorno: {'development' if debug else 'production'}")
    print(f"   Docs:    http://localhost:{port}/api/health\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
