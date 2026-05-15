from app import create_app
from app.database import get_db
from tests.helpers import login


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def test_customers_table_and_order_customer_id_are_migrated(tmp_path):
    app = make_app(tmp_path)

    with app.app_context():
        customer_columns = [
            row["name"]
            for row in get_db().execute("PRAGMA table_info(customers)").fetchall()
        ]
        order_columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(orders)").fetchall()
        }

    assert customer_columns == [
        "id",
        "name",
        "contact",
        "wechat",
        "taobao_nick",
        "source",
        "notes",
        "created_at",
        "updated_at",
    ]
    assert "customer_id" in order_columns


def test_admin_can_create_customer_and_view_customer_list(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.post(
        "/customers",
        data={
            "name": "张三",
            "contact": "13812345678",
            "wechat": "zhangsanwx",
            "taobao_nick": "tb-zhangsan",
            "source": "微信",
            "notes": "老客户",
        },
        follow_redirects=True,
    )

    page = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "张三" in page
    assert "13812345678" in page
    assert "客户列表" in page


def test_new_order_can_link_existing_customer(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    client.post(
        "/customers",
        data={"name": "李四", "contact": "13900000000", "source": "淘宝"},
    )
    with app.app_context():
        customer = get_db().execute("SELECT * FROM customers WHERE name = ?", ("李四",)).fetchone()

    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-CUSTOMER-001",
            "customer_id": str(customer["id"]),
            "source": "淘宝",
            "customer_name": "",
            "customer_contact": "",
            "product_name": "客户关联测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "300",
            "labor_cost": "20",
            "machine_cost": "10",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        order = get_db().execute("SELECT * FROM orders WHERE order_no = ?", ("CF-CUSTOMER-001",)).fetchone()

    assert order["customer_id"] == customer["id"]
    assert order["customer_name"] == "李四"
    assert order["customer_contact"] == "13900000000"


def test_new_order_with_existing_name_prompts_to_link_customer(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    client.post(
        "/customers",
        data={"name": "王五", "contact": "13700000000", "source": "微信"},
    )

    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-CUSTOMER-002",
            "source": "微信",
            "customer_name": "王五",
            "customer_contact": "13700000000",
            "product_name": "重复客户测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "300",
        },
        follow_redirects=True,
    )

    page = response.data.decode("utf-8")
    assert "发现已有客户" in page
    assert "请选择已有客户关联" in page
    with app.app_context():
        order = get_db().execute("SELECT * FROM orders WHERE order_no = ?", ("CF-CUSTOMER-002",)).fetchone()
    assert order is None


def test_customer_detail_shows_history_stats_and_common_specs(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    client.post(
        "/customers",
        data={"name": "赵六", "contact": "13600000000", "source": "线下"},
    )
    with app.app_context():
        customer = get_db().execute("SELECT * FROM customers WHERE name = ?", ("赵六",)).fetchone()

    client.post(
        "/orders/new",
        data={
            "order_no": "CF-CUSTOMER-003",
            "customer_id": str(customer["id"]),
            "source": "线下",
            "product_name": "客户详情测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已完成",
            "final_quote": "500",
            "labor_cost": "30",
            "machine_cost": "20",
        },
    )

    page = client.get(f"/customers/{customer['id']}").data.decode("utf-8")

    assert "客户详情" in page
    assert "历史订单" in page
    assert "累计销售额" in page
    assert "累计利润" in page
    assert "最近下单时间" in page
    assert "常用规格" in page
    assert "CF-CUSTOMER-003" in page
    assert "400×500 / 3mm" in page
