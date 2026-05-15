from app import create_app
from app.database import get_db
from app.repositories import create_order
from tests.helpers import create_user, login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def seed_order(app, order_no, status, delivery_date="2026-05-20"):
    with app.app_context():
        return create_order(
            {
                "order_no": order_no,
                "source": "淘宝",
                "customer_name": f"客户{order_no}",
                "customer_contact": "13800000000",
                "product_name": "碳纤维测试板",
                "material_type": "碳纤维板",
                "specification": "400x500",
                "thickness": "3mm",
                "quantity": 8,
                "board_count": 1,
                "delivery_date": delivery_date,
                "processing_requirements": "切割打孔",
                "notes": "",
                "status": status,
                "sale_unit_price": 0,
                "cost_unit_price": 0,
                "cutting_length": 0,
                "cutting_unit_price": 12,
                "hole_count": 0,
                "hole_unit_price": 2,
                "chamfer_count": 0,
                "chamfer_unit_price": 3,
                "polishing_fee": 0,
                "packaging_fee": 50,
                "shipping_fee": 0,
                "other_fee": 0,
                "is_urgent": 0,
                "urgent_rate": 0.2,
                "include_tax": 0,
                "tax_rate": 0.13,
                "material_quote": 0,
                "cutting_fee": 0,
                "hole_fee": 0,
                "chamfer_fee": 0,
                "quote_subtotal": 0,
                "urgent_fee": 0,
                "tax_fee": 0,
                "quote_total": 0,
                "final_quote": 880,
                "material_cost": 0,
                "labor_cost": 0,
                "machine_cost": 0,
                "packaging_cost": 0,
                "shipping_cost": 0,
                "platform_fee": 0,
                "other_cost": 0,
                "total_cost": 0,
                "profit": 880,
                "margin_rate": 1,
            }
        )


def get_order(app, order_no):
    with app.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_production_board_groups_orders_and_marks_overdue(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    order_id = seed_order(app, "CF-BOARD-001", "待下板", "2026-05-01")
    seed_order(app, "CF-BOARD-002", "加工中")
    seed_order(app, "CF-BOARD-003", "待质检")
    seed_order(app, "CF-BOARD-004", "待包装")
    seed_order(app, "CF-BOARD-005", "已发货")
    login(client)

    response = client.get("/production-board")
    page = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "生产看板" in page
    for status in ["待下板", "加工中", "待质检", "待包装", "已发货"]:
        assert status in page
    assert "CF-BOARD-001" in page
    assert f"/orders/{order_id}" in page
    assert "碳纤维测试板" in page
    assert "数量" in page
    assert "超期" in page
    assert "production-board-grid" in page
    assert "production-card overdue" in page
    assert "下一步" in page


def test_production_user_can_view_board_and_finance_cannot(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "worker", "worker123", "production")
    create_user(app, "finance01", "finance123", "finance")
    seed_order(app, "CF-BOARD-ROLE", "待下板")

    login(client, "worker", "worker123")
    assert client.get("/production-board").status_code == 200

    logout(client)
    login(client, "finance01", "finance123")
    assert client.get("/production-board").status_code == 403


def test_production_board_next_button_returns_to_board(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    order_id = seed_order(app, "CF-BOARD-NEXT", "待下板")
    login(client)

    response = client.post(
        f"/orders/{order_id}/status/next",
        data={"return_to": "production_board", "current_status": "待下板"},
        follow_redirects=True,
    )

    assert response.request.path == "/production-board"
    assert get_order(app, "CF-BOARD-NEXT")["status"] == "加工中"


def test_production_board_css_has_mobile_single_column_layout():
    css = open("static/css/style.css", encoding="utf-8").read()

    assert ".production-board-grid" in css
    assert ".production-card.overdue" in css
    assert "grid-template-columns: 1fr;" in css
