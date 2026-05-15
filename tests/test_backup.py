import zipfile

from app import create_app
from tests.helpers import create_user, login


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "carbon_factory.db"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        }
    )


def test_admin_can_create_backup_zip_with_database_and_uploads(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    login(client)

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    (upload_dir / "drawing.pdf").write_bytes(b"fake drawing")

    response = client.post("/backup", follow_redirects=True)
    page = response.data.decode("utf-8")
    backups = list((tmp_path / "backups").glob("carbon_factory_backup_*.zip"))

    assert response.status_code == 200
    assert "备份成功" in page
    assert len(backups) == 1
    with zipfile.ZipFile(backups[0]) as archive:
        names = archive.namelist()
    assert "carbon_factory.db" in names
    assert "uploads/drawing.pdf" in names


def test_non_admin_cannot_create_backup(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")
    login(client, "sales01", "sales123")

    response = client.post("/backup")

    assert response.status_code == 403
    assert not (tmp_path / "backups").exists()


def test_dashboard_shows_backup_button_only_to_admin(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    create_user(app, "sales01", "sales123", "sales")

    login(client)
    admin_page = client.get("/").data.decode("utf-8")

    client.post("/logout")
    login(client, "sales01", "sales123")
    sales_page = client.get("/").data.decode("utf-8")

    assert "一键备份" in admin_page
    assert 'action="/backup"' in admin_page
    assert "一键备份" not in sales_page
