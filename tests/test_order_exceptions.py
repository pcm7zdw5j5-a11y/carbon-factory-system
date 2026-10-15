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


def create_order(client, order_no="CF-EXC-001"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "异常测试客户",
            "customer_contact": "13800000000",
            "product_name": "异常测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "10",
            "board_count": "2",
            "status": "加工中",
            "final_quote": "880",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_order_exceptions_table_exists(tmp_path):
    app = make_app(tmp_path)

    with app.app_context():
        columns = get_db().execute("PRAGMA table_info(order_exceptions)").fetchall()

    assert [column["name"] for column in columns] == [
        "id",
        "order_id",
        "exception_type",
        "description",
        "handler",
        "result",
        "created_at",
    ]


def test_order_detail_can_add_and_show_exception_record(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client)

    response = client.post(
        f"/orders/{order['id']}/exceptions",
        data={
            "exception_type": "返工",
            "description": "孔位偏差，需要重新加工",
            "handler": "张三",
            "result": "已安排返工",
        },
        follow_redirects=True,
    )
    page = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "异常记录已添加" in page
    assert "异常订单记录" in page
    assert "返工" in page
    assert "孔位偏差，需要重新加工" in page
    assert "张三" in page
    assert "已安排返工" in page

    with app.app_context():
        row = get_db().execute("SELECT * FROM order_exceptions WHERE order_id = ?", (order["id"],)).fetchone()

    assert row["exception_type"] == "返工"
    assert row["handler"] == "张三"


def test_dashboard_shows_unresolved_exception_order_count(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client)
    client.post(
        f"/orders/{order['id']}/exceptions",
        data={
            "exception_type": "材料不足",
            "description": "库存不足",
            "handler": "李四",
            "result": "",
        },
        follow_redirects=False,
    )

    response = client.get("/")
    page = response.data.decode("utf-8")

    assert "未处理异常订单" in page
    assert "<strong>1</strong>" in page


def test_monthly_statistics_show_exception_and_rework_counts(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client)
    client.post(
        f"/orders/{order['id']}/exceptions",
        data={
            "exception_type": "返工",
            "description": "表面划伤返工",
            "handler": "王五",
            "result": "",
        },
        follow_redirects=False,
    )

    order_month = order["created_at"][:7]
    response = client.get(f"/statistics?year={order_month[:4]}&month={int(order_month[5:7])}")
    page = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "异常订单数量" in page
    assert "返工数量" in page
    assert "<strong>1</strong>" in page or "<td>1</td>" in page
