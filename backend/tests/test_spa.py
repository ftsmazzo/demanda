import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def static_dir(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>Demanda</title><div id=root></div>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log('ok')")
    (tmp_path / "segredo.txt").write_text("nao deve vazar")
    return tmp_path


@pytest.fixture
def web(static_dir):
    with TestClient(create_app(database_url=None, static_dir=static_dir)) as client:
        yield client


def test_root_and_screen_routes_serve_the_app(web):
    for path in ("/", "/login", "/painel", "/contatos", "/qualquer/coisa"):
        response = web.get(path)
        assert response.status_code == 200, path
        assert "<div id=root>" in response.text


def test_html_has_security_headers_and_is_not_cached(web):
    response = web.get("/")

    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_served_and_cached_for_a_long_time(web):
    response = web.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "immutable" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_missing_asset_is_a_404_not_the_app(web):
    response = web.get("/assets/nao-existe.js")

    assert response.status_code == 404
    assert "<div id=root>" not in response.text


def test_the_app_never_swallows_api_or_webhook_routes(web):
    for path in ("/api/v1/nao-existe", "/webhooks/nao-existe", "/health/nao-existe"):
        response = web.get(path)
        assert response.status_code == 404, path
        assert "<div id=root>" not in response.text


def test_existing_routes_keep_working(web):
    assert web.get("/health").json() == {"status": "ok"}
    assert web.get("/api/v1/me").status_code == 503  # sem JWT_SECRET configurado


def test_files_outside_assets_and_path_tricks_are_not_exposed(web):
    for path in (
        "/segredo.txt",
        "/assets/../segredo.txt",
        "/assets/%2e%2e/segredo.txt",
        "/..%2fsegredo.txt",
    ):
        response = web.get(path)
        assert "nao deve vazar" not in response.text, path


def test_without_a_static_dir_there_is_no_app(tmp_path):
    with TestClient(create_app(database_url=None)) as client:
        assert client.get("/").status_code == 404
    with TestClient(create_app(database_url=None, static_dir=tmp_path / "vazio")) as client:
        assert client.get("/").status_code == 404


def test_api_responses_are_never_cached_and_carry_the_security_headers(web):
    response = web.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "same-origin"
    assert "max-age" in response.headers["strict-transport-security"]
    assert "permissions-policy" in response.headers


def test_api_paths_get_no_store(web):
    response = web.get("/api/v1/me")

    assert response.headers["cache-control"] == "no-store"


def test_csp_blocks_plugins():
    from app.spa import _CSP

    assert "object-src 'none'" in _CSP
