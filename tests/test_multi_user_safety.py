from app import create_app
from app.database import get_db
from tests.helpers import create_user, login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def create_order(client, order_no="CF-MULTI-001", status="已报价"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "多人测试客户",
            "customer_contact": "13800000000",
            "product_name": "多人测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": status,
            "final_quote": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_sqlite_connection_uses_busy_timeout(tmp_path):
    app = make_app(tmp_path)
    with app.app_context():
        busy_timeout = get_db().execute("PRAGMA busy_timeout").fetchone()[0]

    assert busy_timeout >= 10000
    assert "timeout=10" in open("app/database.py", encoding="utf-8").read()


def test_browser_sessions_are_independent_between_clients(tmp_path):
    app = make_app(tmp_path)
    create_user(app, "sales01", "sales123", "sales")
    create_user(app, "worker01", "worker123", "production")
    sales_browser = app.test_client()
    worker_browser = app.test_client()

    sales_page = login(sales_browser, "sales01", "sales123").data.decode("utf-8")
    worker_page = login(worker_browser, "worker01", "worker123").data.decode("utf-8")

    assert "当前登录：sales01" in sales_page or "sales01" in sales_page
    assert "当前登录：worker01" in worker_page or "worker01" in worker_page

    logout(worker_browser)
    sales_after_worker_logout = sales_browser.get("/").data.decode("utf-8")

    assert "sales01" in sales_after_worker_logout
    assert "登录" not in sales_after_worker_logout[:500]


def test_next_status_rejects_stale_submitted_status(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, status="已报价")

    with app.app_context():
        get_db().execute("UPDATE orders SET status = ? WHERE id = ?", ("已付款", order["id"]))
        get_db().commit()

    response = client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "已报价"},
        follow_redirects=True,
    )

    with app.app_context():
        updated = get_db().execute("SELECT status FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert updated["status"] == "已付款"
    assert "订单状态已被其他人更新，请刷新页面".encode("utf-8") in response.data


def test_status_forms_submit_current_status_and_app_js_disables_buttons(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, status="已报价")
    detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    order_list = client.get("/orders").data.decode("utf-8")
    app_js = open("static/app.js", encoding="utf-8").read()

    assert 'name="current_status" value="已报价"' in detail
    assert 'name="current_status" value="已报价"' in order_list
    assert "submit" in app_js
    assert "disabled = true" in app_js
