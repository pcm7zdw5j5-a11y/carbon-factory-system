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


def create_order(client, order_no, status="待包装"):
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
    assert "shipping_note" in columns


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


def test_next_status_to_shipped_redirects_to_shipping_form_without_tracking_number(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, "CF-SHIP-002")

    response = client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "待包装", "return_to": "list"},
        follow_redirects=False,
    )

    with app.app_context():
        shipped_without_number = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert response.status_code == 302
    assert f"/orders/{order['id']}/shipping" in response.headers["Location"]
    assert shipped_without_number["status"] == "已发货"
    assert not shipped_without_number["tracking_number"]
    assert shipped_without_number["shipped_at"]

    shipping_form = client.get(response.headers["Location"]).data.decode("utf-8")
    order_list = client.get("/orders").data.decode("utf-8")

    assert "填写快递信息" in shipping_form
    assert "待补单号" in order_list

    client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "已发货"},
    )

    with app.app_context():
        completed = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()

    assert completed["status"] == "已完成"


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
            "shipping_note": "客户要求放门卫",
        },
    )

    detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    order_month = order["created_at"][:7]
    stats = client.get(
        f"/statistics?year={order_month[:4]}&month={int(order_month[5:7])}"
    ).data.decode("utf-8")

    assert "发货信息" in detail
    assert "顺丰" in detail
    assert "SF20260514" in detail
    assert "客户要求放门卫" in detail
    assert "快递费总额" in stats
    assert "¥22.00" in stats or "楼22.00" in stats
