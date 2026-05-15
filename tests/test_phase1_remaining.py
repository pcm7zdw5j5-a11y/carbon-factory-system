import io
import zipfile
from pathlib import Path

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


def create_basic_order(client, order_no="CF-PHASE1-001"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "阶段客户",
            "customer_contact": "13800000000",
            "product_name": "碳纤维测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "2",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "600",
            "labor_cost": "30",
            "machine_cost": "20",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def make_simple_xlsx(rows):
    shared_strings = []
    string_indexes = {}

    def shared(value):
        value = str(value)
        if value not in string_indexes:
            string_indexes[value] = len(shared_strings)
            shared_strings.append(value)
        return string_indexes[value]

    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row):
            column = chr(ord("A") + col_index)
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{column}{row_index}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{column}{row_index}" t="s"><v>{shared(value)}</v></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    shared_xml = "".join(f"<si><t>{value}</t></si>" for value in shared_strings)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "")
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{shared_xml}</sst>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(row_xml)}</sheetData></worksheet>',
        )
    output.seek(0)
    return output


def test_taobao_xlsx_import_creates_orders_and_skips_duplicates(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    rows = [
        ["订单编号", "买家昵称", "收货人手机", "商品标题", "购买数量", "实付金额", "卖家备注"],
        ["TB-001", "张三", "13811112222", "碳纤维板 A", 2, 188.5, "加急"],
        ["TB-001", "张三", "13811112222", "碳纤维板 A", 2, 188.5, "重复"],
        ["TB-002", "李四", "13911112222", "碳纤维板 B", 1, 99, ""],
    ]
    response = client.post(
        "/orders/import/taobao",
        data={"taobao_file": (make_simple_xlsx(rows), "taobao.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    page = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "新增 2 条" in page
    assert "跳过 1 条" in page
    with app.app_context():
        first = get_db().execute("SELECT * FROM orders WHERE order_no = 'TB-001'").fetchone()
        second = get_db().execute("SELECT * FROM orders WHERE order_no = 'TB-002'").fetchone()
    assert first["customer_name"] == "张三"
    assert first["customer_contact"] == "13811112222"
    assert first["product_name"] == "碳纤维板 A"
    assert first["quantity"] == 2
    assert first["final_quote"] == 188.5
    assert second is not None


def test_order_attachments_are_archived_in_order_folder_and_downloadable(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)
    order = create_basic_order(client, "CF-ATTACH-001")

    response = client.post(
        f"/orders/{order['id']}/attachments",
        data={
            "attachment_files": [
                (io.BytesIO(b"%PDF"), "报价图纸.pdf"),
                (io.BytesIO(b"zip"), "打包文件.zip"),
            ]
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    page = response.data.decode("utf-8")

    assert response.status_code == 200
    assert "订单附件归档" in page
    assert "报价图纸.pdf" in page
    with app.app_context():
        attachments = get_db().execute(
            "SELECT * FROM order_attachments WHERE order_id = ? ORDER BY id",
            (order["id"],),
        ).fetchall()
    assert len(attachments) == 2
    for attachment in attachments:
        assert attachment["relative_path"].startswith("CF-ATTACH-001/")
        assert (Path(app.config["UPLOAD_FOLDER"]) / attachment["relative_path"]).exists()

    zip_attachment = [item for item in attachments if item["original_filename"].endswith(".zip")][0]
    download = client.get(f"/uploads/{zip_attachment['relative_path']}")
    assert download.status_code == 200
    assert "attachment" in download.headers.get("Content-Disposition", "").lower()


def test_quote_sheet_is_visible_to_sales_but_hidden_from_production_and_has_no_cost_profit(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "worker", "worker123", "production")
    login(client)
    order = create_basic_order(client, "CF-QUOTE-001")

    detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    quote = client.get(f"/orders/{order['id']}/quote").data.decode("utf-8")
    assert "客户报价话术" in detail
    assert "报价单" in detail
    assert "碳纤维工厂客户报价单" in quote
    assert "成本" not in quote
    assert "利润" not in quote

    logout(client)
    login(client, "worker", "worker123")
    forbidden = client.get(f"/orders/{order['id']}/quote")
    assert forbidden.status_code == 403
