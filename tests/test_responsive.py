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


def test_mobile_navigation_and_order_cards_are_rendered(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.get("/orders")
    page = response.data.decode("utf-8")

    assert "mobile-bottom-nav" in page
    assert "mobile-card-list" in page
    assert "order-mobile-card" in page
    assert "desktop-table" in page


def test_mobile_friendly_order_form_upload_and_sections(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.get("/orders/new")
    page = response.data.decode("utf-8")

    assert "form-section-basic" in page
    assert "form-section-upload" in page
    assert "form-section-quote" in page
    assert "form-section-cost" in page
    assert "form-section-production" in page
    assert 'accept=".pdf,.dxf,.dwg,.jpg,.jpeg,.png,.zip,image/*"' in page
    assert 'capture="environment"' in page


def test_css_contains_mobile_media_query_and_no_body_min_width():
    css = open("static/css/style.css", encoding="utf-8").read()

    assert "min-width: 1080px" not in css
    assert "@media (max-width: 768px)" in css
    assert ".mobile-bottom-nav" in css
    assert ".desktop-table" in css


def test_mobile_header_rules_hide_top_navigation_and_use_short_title():
    css = open("static/css/style.css", encoding="utf-8").read()
    template = open("templates/base.html", encoding="utf-8").read()

    assert "brand-short" in template
    assert "碳纤维订单 V1" in template
    assert "mobile-user-label" in template
    assert ".topbar .desktop-nav" in css
    assert ".topbar .mobile-menu" in css
    assert "display: none !important;" in css
    assert "display: flex;" in css
    assert ".mobile-bottom-nav a.active" in css
