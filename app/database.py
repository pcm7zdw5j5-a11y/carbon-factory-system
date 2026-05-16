import os
import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash

from .config import DEFAULT_PRICES
from .services.pricing import normalize_money


def get_db():
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        g.db = sqlite3.connect(db_path, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    app = current_app
    app.teardown_appcontext(close_db)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS price_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            specification TEXT NOT NULL,
            thickness TEXT NOT NULL,
            sale_price REAL NOT NULL,
            cost_price REAL NOT NULL,
            current_stock REAL NOT NULL DEFAULT 0,
            safety_stock REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(specification, thickness)
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            wechat TEXT,
            taobao_nick TEXT,
            source TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            order_no TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_contact TEXT,
            product_name TEXT NOT NULL,
            material_type TEXT,
            specification TEXT NOT NULL,
            thickness TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            board_count REAL NOT NULL DEFAULT 1,
            delivery_date TEXT,
            processing_requirements TEXT,
            notes TEXT,
            status TEXT NOT NULL,
            drawing_filename TEXT,
            drawing_original_name TEXT,
            sale_unit_price REAL NOT NULL DEFAULT 0,
            cost_unit_price REAL NOT NULL DEFAULT 0,
            cutting_length REAL NOT NULL DEFAULT 0,
            cutting_unit_price REAL NOT NULL DEFAULT 12,
            hole_count INTEGER NOT NULL DEFAULT 0,
            hole_unit_price REAL NOT NULL DEFAULT 2,
            chamfer_count INTEGER NOT NULL DEFAULT 0,
            chamfer_unit_price REAL NOT NULL DEFAULT 3,
            polishing_fee REAL NOT NULL DEFAULT 0,
            packaging_fee REAL NOT NULL DEFAULT 50,
            shipping_fee REAL NOT NULL DEFAULT 0,
            other_fee REAL NOT NULL DEFAULT 0,
            is_urgent INTEGER NOT NULL DEFAULT 0,
            urgent_rate REAL NOT NULL DEFAULT 0.2,
            include_tax INTEGER NOT NULL DEFAULT 0,
            tax_rate REAL NOT NULL DEFAULT 0.13,
            material_quote REAL NOT NULL DEFAULT 0,
            cutting_fee REAL NOT NULL DEFAULT 0,
            hole_fee REAL NOT NULL DEFAULT 0,
            chamfer_fee REAL NOT NULL DEFAULT 0,
            quote_subtotal REAL NOT NULL DEFAULT 0,
            urgent_fee REAL NOT NULL DEFAULT 0,
            tax_fee REAL NOT NULL DEFAULT 0,
            quote_total REAL NOT NULL DEFAULT 0,
            final_quote REAL NOT NULL DEFAULT 0,
            material_cost REAL NOT NULL DEFAULT 0,
            labor_cost REAL NOT NULL DEFAULT 0,
            machine_cost REAL NOT NULL DEFAULT 0,
            packaging_cost REAL NOT NULL DEFAULT 0,
            shipping_cost REAL NOT NULL DEFAULT 0,
            platform_fee REAL NOT NULL DEFAULT 0,
            other_cost REAL NOT NULL DEFAULT 0,
            total_cost REAL NOT NULL DEFAULT 0,
            profit REAL NOT NULL DEFAULT 0,
            margin_rate REAL NOT NULL DEFAULT 0,
            shipping_company TEXT,
            tracking_number TEXT,
            shipping_freight REAL NOT NULL DEFAULT 0,
            shipped_at TEXT,
            shipping_note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            changed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action_type TEXT NOT NULL,
            order_no TEXT,
            created_at TEXT NOT NULL,
            before_content TEXT,
            after_content TEXT
        );

        CREATE TABLE IF NOT EXISTS order_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            exception_type TEXT NOT NULL,
            description TEXT,
            handler TEXT,
            result TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS order_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            stored_filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        );
        """
    )
    migrate_price_inventory_columns(db)
    migrate_order_columns(db)
    migrate_order_shipping_columns(db)
    migrate_customer_columns(db)
    migrate_user_columns(db)
    seed_prices(db)
    seed_admin_user(db)
    db.commit()


def table_columns(db, table_name):
    return {
        row["name"]
        for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def add_missing_columns(db, table_name, columns):
    existing_columns = table_columns(db, table_name)
    for column_name, definition in columns.items():
        if column_name not in existing_columns:
            db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def migrate_price_inventory_columns(db):
    add_missing_columns(
        db,
        "price_items",
        {
            "current_stock": "REAL NOT NULL DEFAULT 0",
            "safety_stock": "REAL NOT NULL DEFAULT 0",
        },
    )


def migrate_order_columns(db):
    add_missing_columns(
        db,
        "orders",
        {
            "customer_id": "INTEGER",
            "material_type": "TEXT",
            "quantity": "INTEGER NOT NULL DEFAULT 1",
            "board_count": "REAL NOT NULL DEFAULT 1",
            "delivery_date": "TEXT",
            "processing_requirements": "TEXT",
            "notes": "TEXT",
            "drawing_filename": "TEXT",
            "drawing_original_name": "TEXT",
            "sale_unit_price": "REAL NOT NULL DEFAULT 0",
            "cost_unit_price": "REAL NOT NULL DEFAULT 0",
            "cutting_length": "REAL NOT NULL DEFAULT 0",
            "cutting_unit_price": "REAL NOT NULL DEFAULT 12",
            "hole_count": "INTEGER NOT NULL DEFAULT 0",
            "hole_unit_price": "REAL NOT NULL DEFAULT 2",
            "chamfer_count": "INTEGER NOT NULL DEFAULT 0",
            "chamfer_unit_price": "REAL NOT NULL DEFAULT 3",
            "polishing_fee": "REAL NOT NULL DEFAULT 0",
            "packaging_fee": "REAL NOT NULL DEFAULT 50",
            "shipping_fee": "REAL NOT NULL DEFAULT 0",
            "other_fee": "REAL NOT NULL DEFAULT 0",
            "is_urgent": "INTEGER NOT NULL DEFAULT 0",
            "urgent_rate": "REAL NOT NULL DEFAULT 0.2",
            "include_tax": "INTEGER NOT NULL DEFAULT 0",
            "tax_rate": "REAL NOT NULL DEFAULT 0.13",
            "material_quote": "REAL NOT NULL DEFAULT 0",
            "cutting_fee": "REAL NOT NULL DEFAULT 0",
            "hole_fee": "REAL NOT NULL DEFAULT 0",
            "chamfer_fee": "REAL NOT NULL DEFAULT 0",
            "quote_subtotal": "REAL NOT NULL DEFAULT 0",
            "urgent_fee": "REAL NOT NULL DEFAULT 0",
            "tax_fee": "REAL NOT NULL DEFAULT 0",
            "quote_total": "REAL NOT NULL DEFAULT 0",
            "final_quote": "REAL NOT NULL DEFAULT 0",
            "material_cost": "REAL NOT NULL DEFAULT 0",
            "labor_cost": "REAL NOT NULL DEFAULT 0",
            "machine_cost": "REAL NOT NULL DEFAULT 0",
            "packaging_cost": "REAL NOT NULL DEFAULT 0",
            "shipping_cost": "REAL NOT NULL DEFAULT 0",
            "platform_fee": "REAL NOT NULL DEFAULT 0",
            "other_cost": "REAL NOT NULL DEFAULT 0",
            "total_cost": "REAL NOT NULL DEFAULT 0",
            "profit": "REAL NOT NULL DEFAULT 0",
            "margin_rate": "REAL NOT NULL DEFAULT 0",
        },
    )


def migrate_order_shipping_columns(db):
    add_missing_columns(
        db,
        "orders",
        {
            "shipping_company": "TEXT",
            "tracking_number": "TEXT",
            "shipping_freight": "REAL NOT NULL DEFAULT 0",
            "shipped_at": "TEXT",
            "shipping_note": "TEXT",
        },
    )


def migrate_customer_columns(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            wechat TEXT,
            taobao_nick TEXT,
            source TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    add_missing_columns(db, "orders", {"customer_id": "INTEGER"})


def migrate_user_columns(db):
    add_missing_columns(
        db,
        "users",
        {
            "role": "TEXT NOT NULL DEFAULT 'sales'",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT NOT NULL DEFAULT ''",
        },
    )


def seed_prices(db):
    count = db.execute("SELECT COUNT(*) FROM price_items").fetchone()[0]
    if count:
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for specification, thickness, sale_price in DEFAULT_PRICES:
        cost_price = normalize_money(sale_price * 0.65)
        db.execute(
            """
            INSERT INTO price_items
            (specification, thickness, sale_price, cost_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (specification, thickness, sale_price, cost_price, now, now),
        )


def seed_admin_user(db):
    admin = db.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if admin:
        return
    db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "admin",
            generate_password_hash("admin123"),
            "admin",
            1,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
