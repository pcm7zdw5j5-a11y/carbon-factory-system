import io
import re
from pathlib import Path

from app import create_app
from app.database import get_db
from tests.helpers import login, logout


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def create_order_with_file(client, order_no, filename, content=b"file"):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "上传测试客户",
            "customer_contact": "13800000000",
            "product_name": "上传测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
            "drawing_file": (io.BytesIO(content), filename),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def create_order_without_file(client, order_no):
    response = client.post(
        "/orders/new",
        data={
            "order_no": order_no,
            "source": "淘宝",
            "customer_name": "上传测试客户",
            "customer_contact": "13800000000",
            "product_name": "上传测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with client.application.app_context():
        return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def test_uploaded_file_is_saved_with_order_number_timestamp_and_accessible(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    order = create_order_with_file(client, "CF-UPLOAD-001", "客户 图纸(测试).pdf", b"%PDF-1.4")
    saved_name = order["drawing_filename"]
    saved_path = tmp_path / "uploads" / saved_name

    assert saved_name != order["drawing_original_name"]
    assert re.match(r"CF-UPLOAD-001_\d{14,20}_.+\.pdf$", saved_name)
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"%PDF-1.4"

    detail = client.get(f"/orders/{order['id']}").data.decode("utf-8")
    assert "图纸文件：" in detail
    assert "查看 PDF" in detail
    assert f"/uploads/{saved_name}" in detail

    file_response = client.get(f"/uploads/{saved_name}")
    assert file_response.status_code == 200
    assert file_response.data == b"%PDF-1.4"
    assert "attachment" not in file_response.headers.get("Content-Disposition", "").lower()

    logout(client, follow_redirects=False)
    protected = client.get(f"/uploads/{saved_name}", follow_redirects=False)
    assert protected.status_code == 302
    assert "/login" in protected.headers["Location"]


def test_relative_upload_folder_is_resolved_to_project_root(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": "uploads",
        }
    )

    assert Path(app.config["UPLOAD_FOLDER"]).is_absolute()
    assert Path(app.config["UPLOAD_FOLDER"]).name == "uploads"
    assert Path(app.config["UPLOAD_FOLDER"]).parent == Path(app.root_path).parent


def test_image_thumbnail_and_zip_download_link_are_rendered(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    image_order = create_order_with_file(client, "CF-IMAGE-001", "照片 1.png", b"png")
    image_detail = client.get(f"/orders/{image_order['id']}").data.decode("utf-8")
    assert "drawing-thumbnail" in image_detail
    assert "打开原图" in image_detail

    zip_order = create_order_with_file(client, "CF-ZIP-001", "图纸包.zip", b"zip")
    zip_detail = client.get(f"/orders/{zip_order['id']}").data.decode("utf-8")
    assert "下载文件" in zip_detail
    zip_response = client.get(f"/uploads/{zip_order['drawing_filename']}")
    assert zip_response.status_code == 200
    assert "attachment" in zip_response.headers.get("Content-Disposition", "").lower()


def test_detail_reports_empty_and_missing_drawing_files(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    empty_order = create_order_without_file(client, "CF-NO-DRAWING")
    empty_detail = client.get(f"/orders/{empty_order['id']}").data.decode("utf-8")
    assert "暂未上传图纸。" in empty_detail

    missing_order = create_order_with_file(client, "CF-MISSING-DRAWING", "missing.pdf", b"missing")
    (tmp_path / "uploads" / missing_order["drawing_filename"]).unlink()
    missing_detail = client.get(f"/orders/{missing_order['id']}").data.decode("utf-8")
    assert "图纸文件丢失，请重新上传。" in missing_detail


def test_edit_page_has_reupload_drawing_prompt(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    order = create_order_with_file(client, "CF-REUPLOAD-DRAWING", "old.pdf", b"old")
    edit_page = client.get(f"/orders/{order['id']}/edit").data.decode("utf-8")

    assert "重新上传图纸" in edit_page
    assert "当前图纸" in edit_page


def test_edit_order_keeps_old_file_when_no_new_upload_and_replaces_when_uploaded(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    order = create_order_with_file(client, "CF-EDIT-UPLOAD", "old.pdf", b"old")
    old_name = order["drawing_filename"]

    response = client.post(
        f"/orders/{order['id']}/edit",
        data={
            "order_no": "CF-EDIT-UPLOAD",
            "source": "淘宝",
            "customer_name": "上传测试客户",
            "customer_contact": "13800000000",
            "product_name": "上传测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        unchanged = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
    assert unchanged["drawing_filename"] == old_name

    response = client.post(
        f"/orders/{order['id']}/edit",
        data={
            "order_no": "CF-EDIT-UPLOAD",
            "source": "淘宝",
            "customer_name": "上传测试客户",
            "customer_contact": "13800000000",
            "product_name": "上传测试板",
            "material_type": "碳纤维板",
            "specification": "400×500",
            "thickness": "3mm",
            "quantity": "1",
            "board_count": "1",
            "status": "已报价",
            "final_quote": "500",
            "drawing_file": (io.BytesIO(b"new"), "new.dwg"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        changed = get_db().execute("SELECT * FROM orders WHERE id = ?", (order["id"],)).fetchone()
    assert changed["drawing_filename"] != old_name
    assert (tmp_path / "uploads" / old_name).exists()
    assert (tmp_path / "uploads" / changed["drawing_filename"]).exists()
