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


def create_customer(client, name="历史客户", contact="13500000000"):
    client.post("/customers", data={"name": name, "contact": contact, "source": "微信"})
    with client.application.app_context():
        return get_db().execute("SELECT * FROM customers WHERE name = ?", (name,)).fetchone()


def create_order(client, customer_id, order_no, spec="400×500", thickness="3mm", quote=300, profit=80, quantity=2):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "customer_id": str(customer_id),
            "source": "微信",
            "product_name": "历史价格测试板",
            "material_type": "碳纤维板",
            "specification": spec,
            "thickness": thickness,
            "quantity": str(quantity),
            "board_count": "1",
            "status": "已完成",
            "final_quote": str(quote),
            "labor_cost": "20",
            "machine_cost": str(max(0, quote - 147.55 - 20 - profit)),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_customer_price_history_endpoint_returns_latest_five_and_matching_price(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    customer = create_customer(client)
    for index in range(6):
        create_order(
            client,
            customer["id"],
            f"CF-HISTORY-PRICE-{index}",
            spec="400×500" if index != 1 else "500×600",
            thickness="3mm" if index != 1 else "5mm",
            quote=300 + index * 10,
            profit=60 + index,
            quantity=2 + index,
        )

    response = client.get(f"/customers/{customer['id']}/price-history?specification=400×500&thickness=3mm")
    data = response.get_json()

    assert response.status_code == 200
    assert len(data["orders"]) == 5
    assert data["matching_order"]["specification"] == "400×500"
    assert data["matching_order"]["thickness"] == "3mm"
    assert "final_quote" in data["matching_order"]
    assert "quantity" in data["matching_order"]
    assert "profit" in data["matching_order"]
    assert data["can_view_profit"] is True


def test_sales_price_history_hides_profit(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_user(app, "sales01", "sales123", "sales")
    customer = create_customer(client)
    create_order(client, customer["id"], "CF-HISTORY-SALES", quote=420, profit=120)

    logout(client)
    login(client, "sales01", "sales123")
    response = client.get(f"/customers/{customer['id']}/price-history?specification=400×500&thickness=3mm")
    data = response.get_json()

    assert response.status_code == 200
    assert data["can_view_profit"] is False
    assert data["matching_order"]["final_quote"] == 420
    assert "profit" not in data["matching_order"]
    assert "profit" not in data["orders"][0]


def test_order_form_contains_customer_history_panel_and_data_attributes(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    create_customer(client, name="表单客户", contact="13511112222")

    page = client.get("/orders/new").data.decode("utf-8")

    assert "老客户历史价格提醒" in page
    assert "data-customer-select" in page
    assert "data-customer-history" in page
    assert "data-name=\"表单客户\"" in page
