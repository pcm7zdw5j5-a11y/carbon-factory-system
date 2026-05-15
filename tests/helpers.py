from werkzeug.security import generate_password_hash

from app.database import get_db


def login(client, username="admin", password="admin123", follow_redirects=True):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=follow_redirects,
    )


def logout(client, follow_redirects=True):
    return client.post("/logout", follow_redirects=follow_redirects)


def create_user(app, username, password, role, is_active=1):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, ?, datetime('now', 'localtime'))
            """,
            (username, generate_password_hash(password), role, is_active),
        )
        db.commit()
