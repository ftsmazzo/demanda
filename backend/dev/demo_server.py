"""Servidor de demonstracao local: Postgres embutido, dados ficticios, API e interface juntos.

Uso (a partir de backend/): python dev/demo_server.py   (antes: cd ../frontend && npm run build)
"""

import os
import pathlib
import sys
import tempfile

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "dev"))

import pgserver  # noqa: E402
import psycopg  # noqa: E402
import uvicorn  # noqa: E402
from seed_demo import PASSWORD, TENANT_SLUG, seed  # noqa: E402

from app.main import create_app  # noqa: E402
from app.migrate import apply_migrations  # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
SECRET = "segredo-so-para-demonstracao-local-0123456789"


def main() -> None:
    server = pgserver.get_server(tempfile.mkdtemp(prefix="demanda-demo-"))
    url = server.get_uri()
    apply_migrations(url)
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn)
    dist = BACKEND.parent / "frontend" / "dist"
    app = create_app(database_url=url, jwt_secret=SECRET, static_dir=dist)
    print(
        f"\nDemonstracao em http://localhost:{PORT}  |  empresa: {TENANT_SLUG}  |  senha: {PASSWORD}"
    )
    print(
        "usuarios: carlos@demo.com (socio), rafael@demo.com (gestor), bruno@demo.com (colaborador)\n"
    )
    try:
        uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
    finally:
        server.cleanup()


if __name__ == "__main__":
    main()
