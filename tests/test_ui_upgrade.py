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


def test_base_layout_uses_desktop_sidebar_and_mobile_top_bottom_nav(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    page = client.get("/").data.decode("utf-8")

    assert "app-shell" in page
    assert "sidebar" in page
    assert "app-main" in page
    assert "app-topbar" in page
    assert "碳纤维订单 V1" in page
    assert "mobile-bottom-nav" in page


def test_status_badges_are_rendered_with_data_status(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    client.post(
        "/orders/new",
        data={
            "order_no": "CF-UI-001",
            "source": "淘宝",
            "customer_name": "UI客户",
            "product_name": "UI测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已付款",
            "final_quote": "500",
        },
    )

    page = client.get("/orders").data.decode("utf-8")

    assert 'class="tag status-badge" data-status="已付款"' in page
    assert "money-cell" in page
    assert "profit-positive" in page or "profit-negative" in page


def test_prices_and_users_have_mobile_cards_and_role_badges(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    prices_page = client.get("/prices").data.decode("utf-8")
    users_page = client.get("/users").data.decode("utf-8")

    assert "price-mobile-card" in prices_page
    assert "desktop-table" in prices_page
    assert "user-mobile-card" in users_page
    assert 'class="tag role-badge" data-role="admin"' in users_page
    assert 'class="tag user-status-badge" data-active="1"' in users_page


def test_ui_css_contains_modern_admin_layout_tokens_and_print_hiding():
    css = open("static/css/style.css", encoding="utf-8").read()

    assert "--primary: #0F766E" in css
    assert "--primary-soft: #CCFBF1" in css
    assert "--bg: #F3F4F6" in css
    assert ".sidebar" in css
    assert "width: 220px" in css
    assert ".app-main" in css
    assert ".app-topbar" in css
    assert '[data-status="已付款"]' in css
    assert '[data-status="已取消"]' in css
    assert "@media (max-width: 768px)" in css
    assert ".sidebar" in css and "display: none" in css
    assert "@media print" in css
    assert ".sidebar" in css and ".mobile-bottom-nav" in css
