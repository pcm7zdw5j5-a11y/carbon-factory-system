from app import create_app
from tests.helpers import login


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def test_base_links_canonical_static_css_and_app_js(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    page = client.get("/").data.decode("utf-8")

    assert 'href="/static/style.css' in page
    assert 'src="/static/app.js' in page
    assert "app-layout" in page
    assert "main-content" in page
    assert "sidebar" in page
    assert "topbar" in page


def test_static_style_css_and_app_js_are_served(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    css_response = client.get("/static/style.css")
    js_response = client.get("/static/app.js")
    css = css_response.data.decode("utf-8")

    assert css_response.status_code == 200
    assert js_response.status_code == 200
    assert ".app-layout" in css
    assert ".sidebar" in css
    assert ".main-content" in css
    assert ".card" in css
    assert ".btn-primary" in css
    assert ".dashboard-grid" in css
    assert ".stat-card" in css
    assert ".table" in css
    assert ".badge" in css
