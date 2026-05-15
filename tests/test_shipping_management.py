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


def create_order(client, order_no, status="待发货"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "发货客户",
            "customer_contact": "13800000000",
            "product_name": "碳纤维发货测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "2",
            "board_count": "1",
            "status": status,
            "final_quote": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_orders_table_has_shipping_columns_after_migration(tmp_path):
    app = make_app(tmp_path)

    with app.app_context():
        columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(orders)").fetchall()
        }

    assert "shipping_company" in columns
    assert "tracking_number" in columns
    assert "shipping_freight" in columns
    assert "shipped_at" in columns


def test_sales_and_production_can_save_shipping_info_but_finance_cannot(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_user(app, "sales01", "sales123", "sales")
    create_user(app, "worker", "worker123", "production")
    create_user(app, "finance01", "finance123", "finance")
    order = create_order(client, "CF-SHIP-001")

    logout(client)
    login(client, "sales01", "sales123")
    response = client.post(
        f"/orders/{order['id']}/shipping",
        data={
            "shipping_company": "顺丰",
            "tracking_number": "SF123456789",
            "shipping_freight": "18.5",
            "shipped_at": "2026-05-14 10:30",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    logout(client)
    login(client, "worker", "worker123")
    response = client.post(
        f"/orders/{order['id']}/shipping",
        data={
            "shipping_company": "圆通",
            "tracking_number": "YT987654321",
            "shipping_freight": "20",
            "shipped_at": "2026-05-14 11:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    logout(client)
    login(client, "finance01", "finance123")
    forbidden = client.post(f"/orders/{order['id']}/shipping")

    with app.app_context():
        updated = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert forbidden.status_code == 403
    assert updated["shipping_company"] == "圆通"
    assert updated["tracking_number"] == "YT987654321"
    assert updated["shipping_freight"] == 20
    assert updated["shipped_at"] == "2026-05-14 11:00"


def test_next_status_to_shipped_requires_shipping_info(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, "CF-SHIP-002")

    blocked = client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "待发货"},
        follow_redirects=True,
    )

    with app.app_context():
        unchanged = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert unchanged["status"] == "待发货"
    assert "请先填写快递信息".encode("utf-8") in blocked.data

    client.post(
        f"/orders/{order['id']}/shipping",
        data={
            "shipping_company": "顺丰",
            "tracking_number": "SF0001",
            "shipping_freight": "12",
            "shipped_at": "2026-05-14 12:00",
        },
    )
    client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "待发货"},
    )

    with app.app_context():
        shipped = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert shipped["status"] == "已发货"


def test_order_detail_and_monthly_statistics_show_shipping_info(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, "CF-SHIP-003", status="已发货")
    client.post(
        f"/orders/{order['id']}/shipping",
        data={
            "shipping_company": "顺丰",
            "tracking_number": "SF20260514",
            "shipping_freight": "22",
            "shipped_at": "2026-05-14 13:00",
        },
    )

    detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    stats = client.get("/statistics?year=2026&month=5").data.decode("utf-8")

    assert "发货信息" in detail
    assert "顺丰" in detail
    assert "SF20260514" in detail
    assert "快递费总额" in stats
    assert "¥22.00" in stats or "楼22.00" in stats
