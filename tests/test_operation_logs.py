import io

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


def create_order(client, order_no="CF-LOG-001", status="已报价"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "日志测试客户",
            "customer_contact": "13800000000",
            "product_name": "日志测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "10",
            "board_count": "2",
            "status": status,
            "final_quote": "880",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def log_actions(app):
    with app.app_context():
        return [
            row["action_type"]
            for row in get_db().execute(
                "SELECT action_type FROM operation_logs ORDER BY id"
            ).fetchall()
        ]


def get_order(app, order_id):
    with app.app_context():
        return get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def test_operation_logs_table_exists(tmp_path):
    app = make_app(tmp_path)

    with app.app_context():
        columns = get_db().execute("PRAGMA table_info(operation_logs)").fetchall()

    assert [column["name"] for column in columns] == [
        "id",
        "username",
        "action_type",
        "order_no",
        "created_at",
        "before_content",
        "after_content",
    ]


def test_login_create_status_cancel_delete_are_logged(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()

    login(client)
    order = create_order(client)
    client.post(
        f"/orders/{order['id']}/status/next",
        data={"current_status": "已报价"},
        follow_redirects=False,
    )
    order = get_order(app, order["id"])
    client.post(
        f"/orders/{order['id']}/cancel",
        data={"current_status": order["status"]},
        follow_redirects=False,
    )
    client.post(f"/orders/{order['id']}/delete", follow_redirects=False)

    actions = log_actions(app)
    assert "登录" in actions
    assert "新建订单" in actions
    assert "状态下一步" in actions
    assert "取消订单" in actions
    assert "删除订单" in actions

    with app.app_context():
        status_log = get_db().execute(
            """
            SELECT *
            FROM operation_logs
            WHERE action_type = '状态下一步' AND order_no = 'CF-LOG-001'
            """
        ).fetchone()

    assert status_log["username"] == "admin"
    assert "已报价" in status_log["before_content"]
    assert "已付款" in status_log["after_content"]


def test_edit_quote_cost_upload_and_price_changes_are_logged(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_order(client, "CF-LOG-EDIT")

    response = client.post(
        f"/orders/{order['id']}/edit",
        data={
            "order_no": "CF-LOG-EDIT",
            "source": "淘宝",
            "customer_name": "日志测试客户",
            "customer_contact": "13800000000",
            "product_name": "日志测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "12",
            "board_count": "2",
            "status": "已报价",
            "final_quote": "990",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    client.post(
        f"/orders/{order['id']}/costs/edit",
        data={
            "cost_unit_price": "200",
            "labor_cost": "100",
            "machine_cost": "80",
            "packaging_cost": "20",
            "shipping_cost": "15",
            "platform_fee": "30",
            "other_cost": "10",
        },
        follow_redirects=False,
    )
    client.post(
        "/prices",
        data={
            "specification": "999×999",
            "thickness": "9mm",
            "sale_price": "999",
            "cost_price": "500",
            "current_stock": "3",
            "safety_stock": "5",
        },
        follow_redirects=False,
    )

    actions = log_actions(app)
    assert "编辑订单" in actions
    assert "修改报价" in actions
    assert "修改成本" in actions
    assert "修改价格表" in actions


def test_admin_can_view_operation_logs_and_staff_cannot(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    login(client)
    create_order(client)

    response = client.get("/operation-logs")
    page = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "操作日志" in page
    assert "新建订单" in page

    logout(client)
    login(client, "sales01", "sales123")
    forbidden = client.get("/operation-logs")
    assert forbidden.status_code == 403


def test_uploaded_drawing_is_logged(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    response = client.post(
        "/orders/new",
        data={
            "order_no": "CF-LOG-UPLOAD",
            "source": "淘宝",
            "customer_name": "上传日志客户",
            "customer_contact": "13800000000",
            "product_name": "上传日志板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
            "drawing_file": (io.BytesIO(b"fake pdf"), "drawing.pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        upload_log = get_db().execute(
            """
            SELECT *
            FROM operation_logs
            WHERE action_type = '上传文件' AND order_no = 'CF-LOG-UPLOAD'
            """
        ).fetchone()

    assert upload_log is not None
    assert "drawing.pdf" in upload_log["after_content"]
