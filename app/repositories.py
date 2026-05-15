import json
from datetime import datetime

from werkzeug.security import generate_password_hash

from .database import get_db


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def encode_log_content(content):
    if content is None:
        return None
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str, sort_keys=True)


def create_operation_log(username, action_type, order_no=None, before_content=None, after_content=None):
    db = get_db()
    db.execute(
        """
        INSERT INTO operation_logs
        (username, action_type, order_no, created_at, before_content, after_content)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            username or "system",
            action_type,
            order_no,
            now_text(),
            encode_log_content(before_content),
            encode_log_content(after_content),
        ),
    )
    db.commit()


def list_operation_logs(limit=300):
    return get_db().execute(
        """
        SELECT *
        FROM operation_logs
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def create_order_exception(order_id, data):
    db = get_db()
    db.execute(
        """
        INSERT INTO order_exceptions
        (order_id, exception_type, description, handler, result, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            data["exception_type"],
            data.get("description", ""),
            data.get("handler", ""),
            data.get("result", ""),
            now_text(),
        ),
    )
    db.commit()


def list_order_exceptions(order_id):
    return get_db().execute(
        """
        SELECT *
        FROM order_exceptions
        WHERE order_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (order_id,),
    ).fetchall()


def create_order_attachment(order_id, data):
    db = get_db()
    db.execute(
        """
        INSERT INTO order_attachments
        (order_id, stored_filename, original_filename, relative_path, uploaded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            order_id,
            data["stored_filename"],
            data["original_filename"],
            data["relative_path"],
            now_text(),
        ),
    )
    db.commit()


def list_order_attachments(order_id):
    return get_db().execute(
        """
        SELECT *
        FROM order_attachments
        WHERE order_id = ?
        ORDER BY uploaded_at DESC, id DESC
        """,
        (order_id,),
    ).fetchall()


def get_price_item(specification, thickness):
    return get_db().execute(
        "SELECT * FROM price_items WHERE specification = ? AND thickness = ?",
        (specification, thickness),
    ).fetchone()


def list_price_items():
    return get_db().execute(
        "SELECT * FROM price_items ORDER BY specification, CAST(REPLACE(thickness, 'mm', '') AS REAL)"
    ).fetchall()


def create_price_item(data):
    db = get_db()
    now = now_text()
    db.execute(
        """
        INSERT INTO price_items
        (specification, thickness, sale_price, cost_price, current_stock, safety_stock, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["specification"],
            data["thickness"],
            data["sale_price"],
            data["cost_price"],
            data.get("current_stock", 0),
            data.get("safety_stock", 0),
            now,
            now,
        ),
    )
    db.commit()


def update_price_item(item_id, data):
    db = get_db()
    db.execute(
        """
        UPDATE price_items
        SET specification = ?,
            thickness = ?,
            sale_price = ?,
            cost_price = ?,
            current_stock = ?,
            safety_stock = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            data["specification"],
            data["thickness"],
            data["sale_price"],
            data["cost_price"],
            data.get("current_stock", 0),
            data.get("safety_stock", 0),
            now_text(),
            item_id,
        ),
    )
    db.commit()


def delete_price_item(item_id):
    db = get_db()
    db.execute("DELETE FROM price_items WHERE id = ?", (item_id,))
    db.commit()


def list_purchase_reminders():
    return get_db().execute(
        """
        SELECT
            *,
            ROUND(safety_stock - current_stock, 2) AS suggested_purchase_qty
        FROM price_items
        WHERE COALESCE(safety_stock, 0) > 0
          AND COALESCE(current_stock, 0) < COALESCE(safety_stock, 0)
        ORDER BY specification, CAST(REPLACE(thickness, 'mm', '') AS REAL)
        """
    ).fetchall()


def list_customers():
    return get_db().execute(
        """
        SELECT c.*,
               COUNT(o.id) AS order_count,
               COALESCE(SUM(o.final_quote), 0) AS sales_total
        FROM customers c
        LEFT JOIN orders o
          ON o.customer_id = c.id
          OR (o.customer_id IS NULL AND o.customer_name = c.name)
          OR (c.contact IS NOT NULL AND c.contact <> '' AND o.customer_contact = c.contact)
        GROUP BY c.id
        ORDER BY c.updated_at DESC, c.id DESC
        """
    ).fetchall()


def get_customer(customer_id):
    return get_db().execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()


def find_matching_customers(name=None, contact=None):
    name = (name or "").strip()
    contact = (contact or "").strip()
    if not name and not contact:
        return []
    sql = "SELECT * FROM customers WHERE 1=0"
    params = []
    if name:
        sql += " OR name = ?"
        params.append(name)
    if contact:
        sql += " OR contact = ?"
        params.append(contact)
    sql += " ORDER BY updated_at DESC, id DESC"
    return get_db().execute(sql, params).fetchall()


def create_customer(data):
    db = get_db()
    now = now_text()
    cursor = db.execute(
        """
        INSERT INTO customers (name, contact, wechat, taobao_nick, source, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["name"],
            data.get("contact", ""),
            data.get("wechat", ""),
            data.get("taobao_nick", ""),
            data.get("source", ""),
            data.get("notes", ""),
            now,
            now,
        ),
    )
    db.commit()
    return cursor.lastrowid


def update_customer(customer_id, data):
    db = get_db()
    db.execute(
        """
        UPDATE customers
        SET name = ?,
            contact = ?,
            wechat = ?,
            taobao_nick = ?,
            source = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            data["name"],
            data.get("contact", ""),
            data.get("wechat", ""),
            data.get("taobao_nick", ""),
            data.get("source", ""),
            data.get("notes", ""),
            now_text(),
            customer_id,
        ),
    )
    db.commit()


def list_customer_orders(customer):
    return get_db().execute(
        """
        SELECT *
        FROM orders
        WHERE customer_id = ?
           OR (customer_id IS NULL AND customer_name = ?)
           OR (? <> '' AND customer_contact = ?)
        ORDER BY created_at DESC, id DESC
        """,
        (customer["id"], customer["name"], customer["contact"] or "", customer["contact"] or ""),
    ).fetchall()


def get_customer_stats(customer):
    orders = list_customer_orders(customer)
    total_sales = sum(float(order["final_quote"] or 0) for order in orders)
    total_profit = sum(float(order["profit"] or 0) for order in orders)
    recent_order_time = orders[0]["created_at"] if orders else ""
    return {
        "order_count": len(orders),
        "sales_total": total_sales,
        "profit_total": total_profit,
        "recent_order_time": recent_order_time,
    }


def list_customer_common_specs(customer):
    return get_db().execute(
        """
        SELECT specification, thickness, COUNT(*) AS total
        FROM orders
        WHERE customer_id = ?
           OR (customer_id IS NULL AND customer_name = ?)
           OR (? <> '' AND customer_contact = ?)
        GROUP BY specification, thickness
        ORDER BY total DESC, specification, thickness
        LIMIT 8
        """,
        (customer["id"], customer["name"], customer["contact"] or "", customer["contact"] or ""),
    ).fetchall()


def list_customer_recent_orders(customer, limit=5):
    return get_db().execute(
        """
        SELECT *
        FROM orders
        WHERE customer_id = ?
           OR (customer_id IS NULL AND customer_name = ?)
           OR (? <> '' AND customer_contact = ?)
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (customer["id"], customer["name"], customer["contact"] or "", customer["contact"] or "", limit),
    ).fetchall()


def get_order(order_id):
    return get_db().execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()


def get_order_by_no(order_no):
    return get_db().execute("SELECT * FROM orders WHERE order_no = ?", (order_no,)).fetchone()


def list_users():
    return get_db().execute("SELECT * FROM users ORDER BY id").fetchall()


def create_user(data):
    db = get_db()
    db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["username"],
            generate_password_hash(data["password"]),
            data["role"],
            1,
            now_text(),
        ),
    )
    db.commit()


def update_user_role(user_id, role):
    db = get_db()
    db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    db.commit()


def update_user_password(user_id, password):
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    db.commit()


def update_user_active(user_id, is_active):
    db = get_db()
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if is_active else 0, user_id))
    db.commit()


def delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()


def list_status_history(order_id):
    return get_db().execute(
        """
        SELECT * FROM status_history
        WHERE order_id = ?
        ORDER BY changed_at DESC, id DESC
        """,
        (order_id,),
    ).fetchall()


def list_orders(status=None, source=None, keyword=None):
    sql = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if source:
        sql += " AND source = ?"
        params.append(source)
    if keyword:
        sql += " AND (customer_name LIKE ? OR order_no LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])
    sql += " ORDER BY created_at DESC, id DESC"
    return get_db().execute(sql, params).fetchall()


def search_orders(keyword, limit=50):
    like = f"%{keyword}%"
    return get_db().execute(
        """
        SELECT *
        FROM orders
        WHERE order_no LIKE ?
           OR customer_name LIKE ?
           OR customer_contact LIKE ?
           OR product_name LIKE ?
           OR drawing_original_name LIKE ?
           OR drawing_filename LIKE ?
           OR tracking_number LIKE ?
           OR notes LIKE ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (like, like, like, like, like, like, like, like, limit),
    ).fetchall()


def search_customers(keyword, limit=50):
    like = f"%{keyword}%"
    return get_db().execute(
        """
        SELECT *
        FROM customers
        WHERE name LIKE ?
           OR contact LIKE ?
           OR wechat LIKE ?
           OR taobao_nick LIKE ?
           OR notes LIKE ?
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (like, like, like, like, like, limit),
    ).fetchall()


def search_files(keyword, limit=50):
    like = f"%{keyword}%"
    return get_db().execute(
        """
        SELECT id, order_no, customer_name, product_name, drawing_original_name, drawing_filename, updated_at AS sort_key
        FROM orders
        WHERE drawing_filename IS NOT NULL
          AND drawing_filename <> ''
          AND (drawing_filename LIKE ? OR drawing_original_name LIKE ?)
        UNION ALL
        SELECT o.id,
               o.order_no,
               o.customer_name,
               o.product_name,
               a.original_filename AS drawing_original_name,
               a.relative_path AS drawing_filename,
               a.uploaded_at AS sort_key
        FROM order_attachments a
        JOIN orders o ON o.id = a.order_id
        WHERE a.original_filename LIKE ? OR a.relative_path LIKE ?
        ORDER BY sort_key DESC, id DESC
        LIMIT ?
        """,
        (like, like, like, like, limit),
    ).fetchall()


ORDER_COLUMNS = [
    "customer_id",
    "order_no",
    "source",
    "customer_name",
    "customer_contact",
    "product_name",
    "material_type",
    "specification",
    "thickness",
    "quantity",
    "board_count",
    "delivery_date",
    "processing_requirements",
    "notes",
    "status",
    "drawing_filename",
    "drawing_original_name",
    "sale_unit_price",
    "cost_unit_price",
    "cutting_length",
    "cutting_unit_price",
    "hole_count",
    "hole_unit_price",
    "chamfer_count",
    "chamfer_unit_price",
    "polishing_fee",
    "packaging_fee",
    "shipping_fee",
    "other_fee",
    "is_urgent",
    "urgent_rate",
    "include_tax",
    "tax_rate",
    "material_quote",
    "cutting_fee",
    "hole_fee",
    "chamfer_fee",
    "quote_subtotal",
    "urgent_fee",
    "tax_fee",
    "quote_total",
    "final_quote",
    "material_cost",
    "labor_cost",
    "machine_cost",
    "packaging_cost",
    "shipping_cost",
    "platform_fee",
    "other_cost",
    "total_cost",
    "profit",
    "margin_rate",
]


def create_order(data):
    db = get_db()
    now = now_text()
    columns = ORDER_COLUMNS + ["created_at", "updated_at"]
    values = [data.get(column) for column in ORDER_COLUMNS] + [now, now]
    placeholders = ", ".join(["?"] * len(columns))
    db.execute(
        f"INSERT INTO orders ({', '.join(columns)}) VALUES ({placeholders})",
        values,
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_order(order_id, data):
    db = get_db()
    assignments = ", ".join([f"{column} = ?" for column in ORDER_COLUMNS] + ["updated_at = ?"])
    values = [data.get(column) for column in ORDER_COLUMNS] + [now_text(), order_id]
    db.execute(f"UPDATE orders SET {assignments} WHERE id = ?", values)
    db.commit()


def update_order_status(order_id, status, old_status=None):
    db = get_db()
    changed_at = now_text()
    db.execute(
        "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
        (status, changed_at, order_id),
    )
    if old_status is not None and old_status != status:
        db.execute(
            """
            INSERT INTO status_history (order_id, old_status, new_status, changed_at)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, old_status, status, changed_at),
        )
    db.commit()


def update_order_status_if_current(order_id, old_status, new_status):
    db = get_db()
    changed_at = now_text()
    cursor = db.execute(
        "UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status = ?",
        (new_status, changed_at, order_id, old_status),
    )
    if cursor.rowcount != 1:
        db.rollback()
        return False
    if old_status != new_status:
        db.execute(
            """
            INSERT INTO status_history (order_id, old_status, new_status, changed_at)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, old_status, new_status, changed_at),
        )
    db.commit()
    return True


def update_order_shipping(order_id, data):
    db = get_db()
    db.execute(
        """
        UPDATE orders
        SET shipping_company = ?,
            tracking_number = ?,
            shipping_freight = ?,
            shipped_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            data["shipping_company"],
            data["tracking_number"],
            data["shipping_freight"],
            data["shipped_at"],
            now_text(),
            order_id,
        ),
    )
    db.commit()


def update_order_costs(order_id, data):
    db = get_db()
    db.execute(
        """
        UPDATE orders
        SET cost_unit_price = ?,
            material_cost = ?,
            labor_cost = ?,
            machine_cost = ?,
            packaging_cost = ?,
            shipping_cost = ?,
            platform_fee = ?,
            other_cost = ?,
            total_cost = ?,
            profit = ?,
            margin_rate = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            data["cost_unit_price"],
            data["material_cost"],
            data["labor_cost"],
            data["machine_cost"],
            data["packaging_cost"],
            data["shipping_cost"],
            data["platform_fee"],
            data["other_cost"],
            data["total_cost"],
            data["profit"],
            data["margin_rate"],
            now_text(),
            order_id,
        ),
    )
    db.commit()


def delete_order(order_id):
    db = get_db()
    db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    db.commit()
