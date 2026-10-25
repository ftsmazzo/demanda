"""Serve a interface web (build do frontend) pelo proprio backend: um endereco so, sem CORS."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

logger = logging.getLogger(__name__)

# caminhos que pertencem ao backend e nunca devem cair na SPA
_BACKEND_PREFIXES = ("api/", "webhooks/", "health")

_CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

_HTML_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-cache",
}


class HashedAssets(StaticFiles):
    """Arquivos com hash no nome: podem ser guardados pelo navegador por um ano."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def mount_spa(app: FastAPI, static_dir: str | Path | None) -> bool:
    """Registra a SPA no app. Chame por ultimo, depois de todas as rotas do backend."""
    if not static_dir:
        return False
    root = Path(static_dir)
    index = root / "index.html"
    if not index.is_file():
        logger.warning("STATIC_DIR sem index.html (%s): interface web desligada", root)
        return False

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", HashedAssets(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith(_BACKEND_PREFIXES):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index, headers=_HTML_HEADERS)

    return True
