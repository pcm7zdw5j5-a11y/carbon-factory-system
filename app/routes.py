import json
import os
import sqlite3
import shutil
import zipfile
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    g,
    session,
    url_for,
)
from werkzeug.security import check_password_hash
from werkzeug.utils import safe_join, secure_filename

from .auth import (
    ROLE_LABELS,
    can_advance_status,
    can_cancel_order,
    dashboard_focus_statuses,
    get_user_by_username,
    login_required,
    role_required,
)
from .config import ALLOWED_EXTENSIONS, ORDER_SOURCES, ORDER_STATUSES, SHIPPING_COMPANIES, next_order_status
from .database import get_db
from .repositories import (
    create_order,
    create_customer,
    create_operation_log,
    create_order_attachment,
    create_order_exception,
    create_price_item,
    create_user,
    delete_order,
    delete_price_item,
    delete_user,
    ensure_order_shipped_at,
    get_order,
    get_order_by_no,
    get_customer,
    get_price_item,
    find_matching_customers,
    get_customer_stats,
    list_customer_common_specs,
    list_customer_orders,
    list_customer_recent_orders,
    list_customers,
    list_orders,
    list_operation_logs,
    list_order_attachments,
    list_order_exceptions,
    list_price_items,
    list_purchase_reminders,
    list_status_history,
    list_users,
    now_text,
    search_customers,
    search_files,
    search_orders,
    update_order,
    update_customer,
    update_order_costs,
    update_order_shipping,
    update_order_status,
    update_order_status_if_current,
    update_price_item,
    update_user_active,
    update_user_password,
    update_user_role,
)
from .services.pricing import calculate_cost, calculate_quote, normalize_money
from .services.board_calculator import calculate_rect_board_usage
from .services.statistics import build_monthly_statistics
from .services.taobao_import import read_taobao_order_file


bp = Blueprint("main", __name__)

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
DOWNLOAD_EXTENSIONS = {"dxf", "dwg", "zip"}
REPORT_STATUSES = [
    "待审核",
    "待报价",
    "已报价",
    "已付款",
    "待下板",
    "加工中",
    "待质检",
    "待包装",
    "已发货",
    "已完成",
    "已取消",
]
PRODUCTION_BOARD_STATUSES = ["待下板", "加工中", "待质检", "待包装", "已发货"]
ORDER_LOG_FIELDS = [
    "order_no",
    "source",
    "customer_name",
    "customer_contact",
    "product_name",
    "specification",
    "thickness",
    "quantity",
    "delivery_date",
    "status",
    "final_quote",
    "drawing_filename",
    "drawing_original_name",
]
QUOTE_LOG_FIELDS = [
    "sale_unit_price",
    "board_count",
    "cutting_length",
    "hole_count",
    "chamfer_count",
    "polishing_fee",
    "packaging_fee",
    "shipping_fee",
    "other_fee",
    "is_urgent",
    "include_tax",
    "final_quote",
]
COST_LOG_FIELDS = [
    "cost_unit_price",
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
PRICE_LOG_FIELDS = [
    "specification",
    "thickness",
    "sale_price",
    "cost_price",
    "current_stock",
    "safety_stock",
]
EXCEPTION_TYPES = [
    "图纸问题",
    "客户改图",
    "材料不足",
    "加工失败",
    "返工",
    "延迟发货",
    "客户取消",
    "其他",
]


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("用户名或密码错误。", "error")
        elif not user["is_active"]:
            flash("账号已停用，请联系管理员。", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            create_operation_log(username, "登录")
            if username == "admin" and check_password_hash(user["password_hash"], "admin123"):
                flash("当前使用默认密码 admin123，请尽快在用户管理页面修改默认密码。", "error")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.dashboard"))

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("已退出登录。", "success")
    return redirect(url_for("main.login"))


def to_float(value, default=0):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def to_int(value, default=0):
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_order_no():
    return f"CF{datetime.now().strftime('%Y%m%d%H%M%S')}"


def safe_uploaded_original_name(original_name, extension):
    safe_name = secure_filename(original_name)
    if safe_name and safe_name.lower().endswith(f".{extension}"):
        return safe_name
    safe_stem = secure_filename(original_name.rsplit(".", 1)[0]) or "drawing"
    return f"{safe_stem}.{extension}"


def save_drawing(file_storage, order_no):
    if not file_storage or not file_storage.filename:
        return None, None
    if not allowed_file(file_storage.filename):
        flash("图纸格式不支持，请上传 PDF、DXF、DWG、JPG、PNG 或 ZIP。", "error")
        return None, None

    original_name = file_storage.filename
    extension = original_name.rsplit(".", 1)[1].lower()
    safe_order_no = secure_filename(order_no) or "order"
    safe_original_name = safe_uploaded_original_name(original_name, extension)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    saved_name = f"{safe_order_no}_{timestamp}_{safe_original_name}"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, saved_name))
    return saved_name, original_name


def order_archive_folder(order_no):
    safe_order_no = secure_filename(order_no) or "order"
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    folder = os.path.join(upload_folder, safe_order_no)
    os.makedirs(folder, exist_ok=True)
    return safe_order_no, folder


def archive_existing_upload(stored_filename, original_name, order_no):
    if not stored_filename:
        return None
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    source_path = safe_join(upload_folder, stored_filename)
    if not source_path or not os.path.isfile(source_path):
        return None
    safe_order_no, folder = order_archive_folder(order_no)
    archived_name = os.path.basename(stored_filename)
    target_path = os.path.join(folder, archived_name)
    if not os.path.exists(target_path):
        shutil.copy2(source_path, target_path)
    return {
        "stored_filename": archived_name,
        "original_filename": original_name or archived_name,
        "relative_path": f"{safe_order_no}/{archived_name}",
    }


def save_order_attachment(file_storage, order_no):
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    original_name = file_storage.filename
    extension = original_name.rsplit(".", 1)[1].lower()
    safe_order_no, folder = order_archive_folder(order_no)
    safe_original_name = safe_uploaded_original_name(original_name, extension)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    saved_name = f"{safe_order_no}_{timestamp}_{safe_original_name}"
    file_storage.save(os.path.join(folder, saved_name))
    return {
        "stored_filename": saved_name,
        "original_filename": original_name,
        "relative_path": f"{safe_order_no}/{saved_name}",
    }


def file_display_info(relative_path, original_name=None):
    extension = relative_path.rsplit(".", 1)[1].lower() if "." in relative_path else ""
    return {
        "filename": relative_path,
        "original_name": original_name or os.path.basename(relative_path),
        "extension": extension,
        "is_image": extension in IMAGE_EXTENSIONS,
        "is_pdf": extension == "pdf",
        "is_download": extension in DOWNLOAD_EXTENSIONS,
    }


def order_field(order, field_name):
    if not order:
        return None
    if isinstance(order, dict):
        return order.get(field_name)
    try:
        return order[field_name]
    except (KeyError, IndexError, TypeError):
        return None


def drawing_file_info(order):
    filename = order_field(order, "drawing_filename")
    original_name = order_field(order, "drawing_original_name") or filename
    if not filename:
        return {"status": "empty"}

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    file_path = safe_join(upload_folder, filename)
    extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    exists = bool(file_path and os.path.isfile(file_path))
    return {
        "status": "exists" if exists else "missing",
        "filename": filename,
        "original_name": original_name,
        "extension": extension,
        "is_image": extension in IMAGE_EXTENSIONS,
        "is_pdf": extension == "pdf",
        "is_download": extension in DOWNLOAD_EXTENSIONS,
    }


def price_json():
    return json.dumps(
        [
            {
                "specification": item["specification"],
                "thickness": item["thickness"],
                "sale_price": item["sale_price"],
                "cost_price": item["cost_price"],
            }
            for item in list_price_items()
        ],
        ensure_ascii=False,
    )


def customer_form_data(form):
    return {
        "name": form.get("name", "").strip(),
        "contact": form.get("contact", "").strip(),
        "wechat": form.get("wechat", "").strip(),
        "taobao_nick": form.get("taobao_nick", "").strip(),
        "source": form.get("source", "").strip(),
        "notes": form.get("notes", "").strip(),
    }


def customer_choices():
    return list_customers()


def can_search_customers():
    user = g.get("current_user")
    return bool(user and user["role"] in {"admin", "sales", "finance"})


def can_use_board_calculator():
    user = g.get("current_user")
    return bool(user and user["role"] in {"admin", "sales", "production"})


def current_username():
    user = g.get("current_user")
    return user["username"] if user else "system"


def row_snapshot(row, fields):
    if not row:
        return None
    return {field: order_field(row, field) for field in fields}


def data_snapshot(data, fields):
    return {field: data.get(field) for field in fields}


def snapshots_differ(before, after, fields):
    before_data = row_snapshot(before, fields)
    after_data = data_snapshot(after, fields)
    return before_data != after_data


def todo_orders(db, where_sql, params=()):
    return db.execute(
        f"""
        SELECT *
        FROM orders
        WHERE {where_sql}
        ORDER BY
            CASE WHEN delivery_date IS NULL OR delivery_date = '' THEN 1 ELSE 0 END,
            delivery_date ASC,
            updated_at DESC,
            id DESC
        LIMIT 8
        """,
        params,
    ).fetchall()


def dashboard_todo_groups(db, today):
    role = g.current_user["role"] if g.get("current_user") else ""
    due_statuses_by_role = {
        "admin": ["待审核", "待报价", "已报价", "已付款", "待下板", "加工中", "待质检", "待包装", "待发货", "已发货"],
        "sales": ["待审核", "待报价", "已报价", "已付款", "待发货"],
        "production": ["已付款", "待下板", "加工中", "待质检", "待包装", "待发货", "已发货"],
        "finance": ["已报价", "已付款", "待发货", "已发货"],
    }
    due_statuses = due_statuses_by_role.get(role, [])
    due_orders = []
    if due_statuses:
        placeholders = ",".join(["?"] * len(due_statuses))
        due_orders = todo_orders(
            db,
            f"delivery_date = ? AND status IN ({placeholders})",
            (today, *due_statuses),
        )
    definitions = [
        {
            "key": "due_today",
            "title": "今天到期",
            "hint": "交期为今天且尚未完成的订单",
            "roles": {"admin", "sales", "production", "finance"},
            "orders": due_orders,
        },
        {
            "key": "pending_quote",
            "title": "待报价",
            "hint": "需要销售尽快报价",
            "roles": {"admin", "sales"},
            "orders": todo_orders(db, "status = '待报价'"),
        },
        {
            "key": "paid_not_boarded",
            "title": "已付款未下板",
            "hint": "已收款，等待生产接单下板",
            "roles": {"admin", "sales", "production"},
            "orders": todo_orders(db, "status = '已付款'"),
        },
        {
            "key": "processing_timeout",
            "title": "加工中超时",
            "hint": "加工中且超过 1 天未更新",
            "roles": {"admin", "production"},
            "orders": todo_orders(db, "status = '加工中' AND substr(updated_at, 1, 10) < ?", (today,)),
        },
        {
            "key": "pending_shipping",
            "title": "待发货",
            "hint": "生产结束，等待录入发货信息",
            "roles": {"admin", "sales", "finance"},
            "orders": todo_orders(db, "status = '待发货'"),
        },
    ]
    return [item for item in definitions if role in item["roles"]]


def hydrate_order_customer(data):
    customer_id = to_int(data.get("customer_id"))
    if not customer_id:
        return
    customer = get_customer(customer_id)
    if not customer:
        data["customer_id"] = None
        return
    data["customer_id"] = customer["id"]
    data["customer_name"] = customer["name"]
    data["customer_contact"] = customer["contact"] or data["customer_contact"]
    if not data["source"] and customer["source"]:
        data["source"] = customer["source"]


def maybe_create_order_customer(data):
    if data.get("customer_id"):
        return
    if not data.get("customer_name"):
        return
    matches = find_matching_customers(data["customer_name"], data.get("customer_contact"))
    if matches:
        return
    customer_id = create_customer(
        {
            "name": data["customer_name"],
            "contact": data.get("customer_contact", ""),
            "source": data.get("source", ""),
            "notes": "",
        }
    )
    data["customer_id"] = customer_id


def shipping_info_complete(order):
    return bool(
        order_field(order, "shipping_company")
        and order_field(order, "tracking_number")
        and order_field(order, "shipped_at")
    )


def shipping_return_url(order_id, return_to=None):
    target = return_to or request.values.get("return_to")
    if target == "production_board":
        return url_for("main.production_board")
    if target == "list":
        return url_for("main.orders")
    return url_for("main.order_detail", order_id=order_id)


def create_backup_archive():
    database_path = os.path.abspath(current_app.config["DATABASE"])
    upload_folder = os.path.abspath(current_app.config["UPLOAD_FOLDER"])
    backup_dir = os.path.join(os.path.dirname(database_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"carbon_factory_backup_{timestamp}.zip")
    temp_database_copy = os.path.join(backup_dir, f"carbon_factory_{timestamp}.db")

    source = sqlite3.connect(database_path, timeout=10)
    try:
        target = sqlite3.connect(temp_database_copy, timeout=10)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    try:
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_database_copy, "carbon_factory.db")
            if os.path.isdir(upload_folder):
                for root, _, files in os.walk(upload_folder):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        relative_path = os.path.relpath(file_path, upload_folder)
                        archive.write(file_path, os.path.join("uploads", relative_path).replace("\\", "/"))
    finally:
        if os.path.exists(temp_database_copy):
            os.remove(temp_database_copy)

    return backup_path


def build_order_data(form, existing=None):
    order_no = form.get("order_no", "").strip() or generate_order_no()
    specification = form.get("specification", "").strip()
    thickness = form.get("thickness", "").strip()
    price_item = get_price_item(specification, thickness)
    sale_unit_price = price_item["sale_price"] if price_item else to_float(form.get("sale_unit_price"))
    cost_unit_price = price_item["cost_price"] if price_item else to_float(form.get("cost_unit_price"))

    board_count = to_float(form.get("board_count"), 1)
    quote_inputs = {
        "sale_unit_price": sale_unit_price,
        "board_count": board_count,
        "cutting_length": to_float(form.get("cutting_length")),
        "cutting_unit_price": to_float(form.get("cutting_unit_price"), 12),
        "hole_count": to_int(form.get("hole_count")),
        "hole_unit_price": to_float(form.get("hole_unit_price"), 2),
        "chamfer_count": to_int(form.get("chamfer_count")),
        "chamfer_unit_price": to_float(form.get("chamfer_unit_price"), 3),
        "polishing_fee": to_float(form.get("polishing_fee")),
        "packaging_fee": to_float(form.get("packaging_fee"), 50),
        "shipping_fee": to_float(form.get("shipping_fee")),
        "other_fee": to_float(form.get("other_fee")),
        "is_urgent": form.get("is_urgent") == "1",
        "urgent_rate": to_float(form.get("urgent_rate"), 0.2),
        "include_tax": form.get("include_tax") == "1",
        "tax_rate": to_float(form.get("tax_rate"), 0.13),
    }
    quote = calculate_quote(**quote_inputs)
    final_quote = to_float(form.get("final_quote"), quote["quote_total"])
    if final_quote <= 0:
        final_quote = quote["quote_total"]

    cost_inputs = {
        "cost_unit_price": cost_unit_price,
        "board_count": board_count,
        "labor_cost": to_float(form.get("labor_cost")),
        "machine_cost": to_float(form.get("machine_cost")),
        "packaging_cost": to_float(form.get("packaging_cost")),
        "shipping_cost": to_float(form.get("shipping_cost")),
        "platform_fee": to_float(form.get("platform_fee")),
        "other_cost": to_float(form.get("other_cost")),
        "final_quote": final_quote,
    }
    cost = calculate_cost(**cost_inputs)

    drawing_filename = existing["drawing_filename"] if existing else None
    drawing_original_name = existing["drawing_original_name"] if existing else None
    saved_name, original_name = save_drawing(request.files.get("drawing_file"), order_no)
    if saved_name:
        drawing_filename = saved_name
        drawing_original_name = original_name

    data = {
        "customer_id": to_int(form.get("customer_id")) or None,
        "order_no": order_no,
        "source": form.get("source", "淘宝"),
        "customer_name": form.get("customer_name", "").strip(),
        "customer_contact": form.get("customer_contact", "").strip(),
        "product_name": form.get("product_name", "").strip(),
        "material_type": form.get("material_type", "").strip() or "碳纤维板",
        "specification": specification,
        "thickness": thickness,
        "quantity": to_int(form.get("quantity"), 1),
        "board_count": board_count,
        "delivery_date": form.get("delivery_date", ""),
        "processing_requirements": form.get("processing_requirements", "").strip(),
        "notes": form.get("notes", "").strip(),
        "status": form.get("status", "待审核"),
        "drawing_filename": drawing_filename,
        "drawing_original_name": drawing_original_name,
        "sale_unit_price": sale_unit_price,
        "cost_unit_price": cost_unit_price,
        **quote_inputs,
        **quote,
        "is_urgent": 1 if quote_inputs["is_urgent"] else 0,
        "include_tax": 1 if quote_inputs["include_tax"] else 0,
        "final_quote": normalize_money(final_quote),
        **cost_inputs,
        **cost,
    }
    hydrate_order_customer(data)
    return data


def import_amount(value):
    text = str(value or "").replace(",", "").replace("¥", "").replace("￥", "").strip()
    text = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    return to_float(text)


def build_import_order_data(record):
    order_no = record.get("order_no", "").strip() or generate_order_no()
    quantity = max(to_int(record.get("quantity"), 1), 1)
    final_quote = normalize_money(import_amount(record.get("final_quote")))
    board_count = 1
    quote_inputs = {
        "sale_unit_price": final_quote,
        "board_count": board_count,
        "cutting_length": 0,
        "cutting_unit_price": 12,
        "hole_count": 0,
        "hole_unit_price": 2,
        "chamfer_count": 0,
        "chamfer_unit_price": 3,
        "polishing_fee": 0,
        "packaging_fee": 0,
        "shipping_fee": 0,
        "other_fee": 0,
        "is_urgent": False,
        "urgent_rate": 0.2,
        "include_tax": False,
        "tax_rate": 0.13,
    }
    quote = calculate_quote(**quote_inputs)
    cost_inputs = {
        "cost_unit_price": 0,
        "board_count": board_count,
        "labor_cost": 0,
        "machine_cost": 0,
        "packaging_cost": 0,
        "shipping_cost": 0,
        "platform_fee": 0,
        "other_cost": 0,
        "final_quote": final_quote,
    }
    cost = calculate_cost(**cost_inputs)
    data = {
        "customer_id": None,
        "order_no": order_no,
        "source": "淘宝",
        "customer_name": record.get("customer_name", "").strip() or "淘宝客户",
        "customer_contact": record.get("customer_contact", "").strip(),
        "product_name": record.get("product_name", "").strip() or "淘宝商品",
        "material_type": "碳纤维板",
        "specification": "400×500",
        "thickness": "3mm",
        "quantity": quantity,
        "board_count": board_count,
        "delivery_date": "",
        "processing_requirements": "",
        "notes": record.get("notes", "").strip(),
        "status": "待审核",
        "drawing_filename": None,
        "drawing_original_name": None,
        "sale_unit_price": final_quote,
        "cost_unit_price": 0,
        **quote_inputs,
        **quote,
        "is_urgent": 0,
        "include_tax": 0,
        "final_quote": final_quote,
        **cost_inputs,
        **cost,
    }
    hydrate_order_customer(data)
    return data


def attachment_infos(order_id):
    return [
        file_display_info(item["relative_path"], item["original_filename"])
        for item in list_order_attachments(order_id)
    ]


@bp.route("/")
def dashboard():
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")
    month = date.today().strftime("%Y-%m")
    stats = {
        "today_orders": db.execute(
            "SELECT COUNT(*) FROM orders WHERE substr(created_at, 1, 10) = ?", (today,)
        ).fetchone()[0],
        "month_orders": db.execute(
            "SELECT COUNT(*) FROM orders WHERE substr(created_at, 1, 7) = ?", (month,)
        ).fetchone()[0],
        "month_sales": db.execute(
            "SELECT COALESCE(SUM(final_quote), 0) FROM orders WHERE substr(created_at, 1, 7) = ?",
            (month,),
        ).fetchone()[0],
        "month_profit": db.execute(
            "SELECT COALESCE(SUM(profit), 0) FROM orders WHERE substr(created_at, 1, 7) = ?",
            (month,),
        ).fetchone()[0],
        "pending_board": db.execute("SELECT COUNT(*) FROM orders WHERE status = '待下板'").fetchone()[0],
        "processing": db.execute("SELECT COUNT(*) FROM orders WHERE status = '加工中'").fetchone()[0],
        "shipping": db.execute("SELECT COUNT(*) FROM orders WHERE status = '待发货'").fetchone()[0],
        "unresolved_exception_orders": db.execute(
            """
            SELECT COUNT(DISTINCT order_id)
            FROM order_exceptions
            WHERE TRIM(COALESCE(result, '')) = ''
            """
        ).fetchone()[0],
        "low_profit_orders": db.execute(
            """
            SELECT COUNT(*)
            FROM orders
            WHERE profit < 0 OR margin_rate < 20
            """
        ).fetchone()[0],
        "month_cost": db.execute(
            "SELECT COALESCE(SUM(total_cost), 0) FROM orders WHERE substr(created_at, 1, 7) = ?",
            (month,),
        ).fetchone()[0],
    }
    latest_orders = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 8").fetchall()
    purchase_reminders = list_purchase_reminders()
    focus_statuses = dashboard_focus_statuses()
    focus_orders = []
    if focus_statuses:
        placeholders = ",".join(["?"] * len(focus_statuses))
        focus_orders = db.execute(
            f"SELECT * FROM orders WHERE status IN ({placeholders}) ORDER BY updated_at DESC LIMIT 12",
            focus_statuses,
        ).fetchall()
    todo_groups = dashboard_todo_groups(db, today)
    return render_template(
        "dashboard.html",
        stats=stats,
        todo_groups=todo_groups,
        latest_orders=latest_orders,
        focus_statuses=focus_statuses,
        focus_orders=focus_orders,
        purchase_reminders=purchase_reminders,
        current_date=date.today().strftime("%Y-%m-%d"),
    )


@bp.route("/search")
@login_required
def global_search():
    keyword = request.args.get("q", "").strip()
    order_results = []
    customer_results = []
    file_results = []
    if keyword:
        order_results = search_orders(keyword)
        if can_search_customers():
            customer_results = search_customers(keyword)
        file_results = search_files(keyword)
    return render_template(
        "search.html",
        keyword=keyword,
        order_results=order_results,
        customer_results=customer_results,
        file_results=file_results,
    )


@bp.route("/board-calculator", methods=["GET", "POST"])
@role_required("admin", "sales", "production")
def board_calculator():
    result = None
    form_data = {
        "board_width": request.form.get("board_width", "400"),
        "board_height": request.form.get("board_height", "500"),
        "part_width": request.form.get("part_width", ""),
        "part_height": request.form.get("part_height", ""),
        "quantity": request.form.get("quantity", "1"),
        "margin": request.form.get("margin", "0"),
        "spacing": request.form.get("spacing", "0"),
    }
    if request.method == "POST":
        result = calculate_rect_board_usage(**form_data)
    return render_template("board_calculator.html", result=result, form_data=form_data)


@bp.route("/backup", methods=["POST"])
@role_required("admin")
def backup():
    backup_path = create_backup_archive()
    flash(f"备份成功：{os.path.basename(backup_path)}", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/orders")
@role_required("admin", "sales", "production", "finance")
def orders():
    filters = {
        "status": request.args.get("status", ""),
        "source": request.args.get("source", ""),
        "keyword": request.args.get("keyword", ""),
    }
    rows = list_orders()
    return render_template(
        "orders/list.html",
        orders=rows,
        filters=filters,
        statuses=ORDER_STATUSES,
        sources=ORDER_SOURCES,
        next_order_status=next_order_status,
    )


@bp.route("/orders/import/taobao", methods=["GET", "POST"])
@role_required("admin", "sales")
def taobao_import():
    result = None
    if request.method == "POST":
        upload = request.files.get("taobao_file")
        if not upload or not upload.filename:
            flash("请先选择淘宝订单 Excel 文件。", "error")
        else:
            try:
                records = read_taobao_order_file(upload)
            except (ValueError, zipfile.BadZipFile) as exc:
                flash(str(exc), "error")
            else:
                imported = []
                skipped = []
                errors = []
                for index, record in enumerate(records, start=2):
                    data = build_import_order_data(record)
                    if not data["order_no"]:
                        errors.append(f"第 {index} 行缺少订单编号")
                        continue
                    if get_order_by_no(data["order_no"]):
                        skipped.append(data["order_no"])
                        continue
                    order_id = create_order(data)
                    imported.append({"id": order_id, "order_no": data["order_no"]})
                    create_operation_log(
                        current_username(),
                        "淘宝订单导入",
                        data["order_no"],
                        after_content=data_snapshot(data, ORDER_LOG_FIELDS + QUOTE_LOG_FIELDS),
                    )
                result = {
                    "total": len(records),
                    "imported": imported,
                    "skipped": skipped,
                    "errors": errors,
                }
                flash(f"淘宝订单导入完成：新增 {len(imported)} 条，跳过 {len(skipped)} 条。", "success")

    return render_template("orders/import_taobao.html", result=result)


@bp.route("/production-board")
@role_required("admin", "production")
def production_board():
    db = get_db()
    board_columns = []
    for status in PRODUCTION_BOARD_STATUSES:
        orders = db.execute(
            """
            SELECT *
            FROM orders
            WHERE status = ?
            ORDER BY
                CASE WHEN delivery_date IS NULL OR delivery_date = '' THEN 1 ELSE 0 END,
                delivery_date ASC,
                updated_at DESC,
                id DESC
            """,
            (status,),
        ).fetchall()
        board_columns.append({"status": status, "orders": orders})

    return render_template(
        "orders/production_board.html",
        board_columns=board_columns,
        today=date.today().strftime("%Y-%m-%d"),
        next_order_status=next_order_status,
    )


@bp.route("/customers", methods=["GET", "POST"])
@role_required("admin", "sales", "finance")
def customers():
    if request.method == "POST":
        data = customer_form_data(request.form)
        if not data["name"]:
            flash("客户名称必须填写。", "error")
        else:
            create_customer(data)
            flash("客户已新增。", "success")
            return redirect(url_for("main.customers"))

    return render_template(
        "customers/list.html",
        customers=list_customers(),
        sources=ORDER_SOURCES,
    )


@bp.route("/customers/<int:customer_id>", methods=["GET", "POST"])
@role_required("admin", "sales", "finance")
def customer_detail(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        abort(404)
    if request.method == "POST":
        data = customer_form_data(request.form)
        if not data["name"]:
            flash("客户名称必须填写。", "error")
        else:
            update_customer(customer_id, data)
            flash("客户信息已更新。", "success")
            return redirect(url_for("main.customer_detail", customer_id=customer_id))

    customer = get_customer(customer_id)
    return render_template(
        "customers/detail.html",
        customer=customer,
        orders=list_customer_orders(customer),
        stats=get_customer_stats(customer),
        common_specs=list_customer_common_specs(customer),
        sources=ORDER_SOURCES,
    )


def serialize_history_order(order, include_profit=False):
    data = {
        "id": order["id"],
        "order_no": order["order_no"],
        "product_name": order["product_name"],
        "specification": order["specification"],
        "thickness": order["thickness"],
        "quantity": order["quantity"],
        "final_quote": order["final_quote"],
        "created_at": order["created_at"],
    }
    if include_profit:
        data["profit"] = order["profit"]
    return data


@bp.route("/customers/<int:customer_id>/price-history")
@role_required("admin", "sales", "finance")
def customer_price_history(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        abort(404)
    specification = request.args.get("specification", "").strip()
    thickness = request.args.get("thickness", "").strip()
    can_view_profit = bool(g.get("current_user") and g.current_user["role"] in {"admin", "finance"})
    orders = list_customer_recent_orders(customer, limit=5)
    matching_order = None
    for order in orders:
        if order["specification"] == specification and order["thickness"] == thickness:
            matching_order = order
            break
    return jsonify(
        {
            "can_view_profit": can_view_profit,
            "orders": [serialize_history_order(order, can_view_profit) for order in orders],
            "matching_order": serialize_history_order(matching_order, can_view_profit) if matching_order else None,
        }
    )


@bp.route("/orders/new", methods=["GET", "POST"])
@role_required("admin", "sales")
def order_new():
    duplicate_customers = []
    form_order = {}
    if request.method == "POST":
        data = build_order_data(request.form)
        form_order = data
        duplicate_customers = []
        if not data.get("customer_id") and request.form.get("confirm_new_customer") != "1":
            duplicate_customers = find_matching_customers(data["customer_name"], data.get("customer_contact"))
        if not data["customer_name"] or not data["product_name"]:
            flash("客户名称和产品名称必须填写。", "error")
        elif duplicate_customers:
            flash("发现已有客户，请选择已有客户关联，或勾选确认新建不关联。", "error")
        elif get_order_by_no := get_db().execute(
            "SELECT id FROM orders WHERE order_no = ?", (data["order_no"],)
        ).fetchone():
            flash(f"订单编号 {data['order_no']} 已存在，请换一个编号。", "error")
        else:
            order_id = create_order(data)
            archived_drawing = archive_existing_upload(
                data.get("drawing_filename"),
                data.get("drawing_original_name"),
                data["order_no"],
            )
            if archived_drawing:
                create_order_attachment(order_id, archived_drawing)
            create_operation_log(
                current_username(),
                "新建订单",
                data["order_no"],
                after_content=data_snapshot(data, ORDER_LOG_FIELDS),
            )
            if data.get("drawing_filename"):
                create_operation_log(
                    current_username(),
                    "上传文件",
                    data["order_no"],
                    after_content={
                        "drawing_filename": data.get("drawing_filename"),
                        "drawing_original_name": data.get("drawing_original_name"),
                    },
                )
            flash("订单已保存。", "success")
            return redirect(url_for("main.order_detail", order_id=order_id))

    return render_template(
        "orders/form.html",
        order=form_order,
        title="新建订单",
        statuses=ORDER_STATUSES,
        sources=ORDER_SOURCES,
        prices_json=price_json(),
        drawing_file=drawing_file_info({}),
        customers=customer_choices(),
        duplicate_customers=duplicate_customers,
    )


@bp.route("/orders/<int:order_id>")
@role_required("admin", "sales", "production", "finance")
def order_detail(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    return render_template(
        "orders/detail.html",
        order=order,
        status_history=list_status_history(order_id),
        order_exceptions=list_order_exceptions(order_id),
        exception_types=EXCEPTION_TYPES,
        next_order_status=next_order_status,
        drawing_file=drawing_file_info(order),
        attachments=attachment_infos(order_id),
    )


@bp.route("/orders/<int:order_id>/attachments", methods=["POST"])
@role_required("admin", "sales", "production")
def order_attachment_upload(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    files = request.files.getlist("attachment_files")
    uploaded = []
    skipped = 0
    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue
        attachment = save_order_attachment(file_storage, order["order_no"])
        if not attachment:
            skipped += 1
            continue
        create_order_attachment(order_id, attachment)
        uploaded.append(attachment)

    if uploaded:
        create_operation_log(
            current_username(),
            "上传文件",
            order["order_no"],
            after_content={"attachments": uploaded},
        )
        flash(f"已上传 {len(uploaded)} 个附件。", "success")
    if skipped:
        flash("部分文件格式不支持，已跳过。", "error")
    if not uploaded and not skipped:
        flash("请先选择要上传的附件。", "error")
    return redirect(url_for("main.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/quote")
@role_required("admin", "sales", "finance")
def order_quote(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    return render_template("orders/quote.html", order=order)


@bp.route("/orders/<int:order_id>/exceptions", methods=["POST"])
@role_required("admin", "sales", "production", "finance")
def order_exception_add(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)

    data = {
        "exception_type": request.form.get("exception_type", "").strip(),
        "description": request.form.get("description", "").strip(),
        "handler": request.form.get("handler", "").strip() or current_username(),
        "result": request.form.get("result", "").strip(),
    }
    if data["exception_type"] not in EXCEPTION_TYPES:
        flash("请选择正确的异常类型。", "error")
    elif not data["description"]:
        flash("请填写异常说明。", "error")
    else:
        create_order_exception(order_id, data)
        flash("异常记录已添加。", "success")
    return redirect(url_for("main.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@role_required("admin", "sales")
def order_edit(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    order_dict = dict(order)
    duplicate_customers = []
    if request.method == "POST":
        data = build_order_data(request.form, existing=order)
        duplicate = get_db().execute(
            "SELECT id FROM orders WHERE order_no = ? AND id <> ?",
            (data["order_no"], order_id),
        ).fetchone()
        if duplicate:
            flash(f"订单编号 {data['order_no']} 已存在，请换一个编号。", "error")
        else:
            before_order = dict(order)
            update_order(order_id, data)
            create_operation_log(
                current_username(),
                "编辑订单",
                data["order_no"],
                before_content=row_snapshot(before_order, ORDER_LOG_FIELDS),
                after_content=data_snapshot(data, ORDER_LOG_FIELDS),
            )
            if snapshots_differ(before_order, data, QUOTE_LOG_FIELDS):
                create_operation_log(
                    current_username(),
                    "修改报价",
                    data["order_no"],
                    before_content=row_snapshot(before_order, QUOTE_LOG_FIELDS),
                    after_content=data_snapshot(data, QUOTE_LOG_FIELDS),
                )
            if before_order.get("drawing_filename") != data.get("drawing_filename"):
                archived_drawing = archive_existing_upload(
                    data.get("drawing_filename"),
                    data.get("drawing_original_name"),
                    data["order_no"],
                )
                if archived_drawing:
                    create_order_attachment(order_id, archived_drawing)
                create_operation_log(
                    current_username(),
                    "上传文件",
                    data["order_no"],
                    before_content={
                        "drawing_filename": before_order.get("drawing_filename"),
                        "drawing_original_name": before_order.get("drawing_original_name"),
                    },
                    after_content={
                        "drawing_filename": data.get("drawing_filename"),
                        "drawing_original_name": data.get("drawing_original_name"),
                    },
                )
            flash("订单已更新。", "success")
            return redirect(url_for("main.order_detail", order_id=order_id))

    return render_template(
        "orders/form.html",
        order=order_dict,
        title="编辑订单",
        statuses=ORDER_STATUSES,
        sources=ORDER_SOURCES,
        prices_json=price_json(),
        drawing_file=drawing_file_info(order),
        customers=customer_choices(),
        duplicate_customers=duplicate_customers,
    )


@bp.route("/orders/<int:order_id>/costs/edit", methods=["GET", "POST"])
@role_required("admin", "finance")
def order_cost_edit(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    if request.method == "POST":
        cost_inputs = {
            "cost_unit_price": to_float(request.form.get("cost_unit_price"), order["cost_unit_price"]),
            "board_count": order["board_count"],
            "labor_cost": to_float(request.form.get("labor_cost")),
            "machine_cost": to_float(request.form.get("machine_cost")),
            "packaging_cost": to_float(request.form.get("packaging_cost")),
            "shipping_cost": to_float(request.form.get("shipping_cost")),
            "platform_fee": to_float(request.form.get("platform_fee")),
            "other_cost": to_float(request.form.get("other_cost")),
            "final_quote": order["final_quote"],
        }
        cost = calculate_cost(**cost_inputs)
        before_cost = row_snapshot(order, COST_LOG_FIELDS)
        after_cost = {
            "cost_unit_price": cost_inputs["cost_unit_price"],
            "material_cost": cost["material_cost"],
            "labor_cost": cost_inputs["labor_cost"],
            "machine_cost": cost_inputs["machine_cost"],
            "packaging_cost": cost_inputs["packaging_cost"],
            "shipping_cost": cost_inputs["shipping_cost"],
            "platform_fee": cost_inputs["platform_fee"],
            "other_cost": cost_inputs["other_cost"],
            "total_cost": cost["total_cost"],
            "profit": cost["profit"],
            "margin_rate": cost["margin_rate"],
        }
        update_order_costs(
            order_id,
            {
                "cost_unit_price": cost_inputs["cost_unit_price"],
                "labor_cost": cost_inputs["labor_cost"],
                "machine_cost": cost_inputs["machine_cost"],
                "packaging_cost": cost_inputs["packaging_cost"],
                "shipping_cost": cost_inputs["shipping_cost"],
                "platform_fee": cost_inputs["platform_fee"],
                "other_cost": cost_inputs["other_cost"],
                **cost,
            },
        )
        create_operation_log(
            current_username(),
            "修改成本",
            order["order_no"],
            before_content=before_cost,
            after_content=after_cost,
        )
        flash("成本信息已更新。", "success")
        return redirect(url_for("main.order_detail", order_id=order_id))

    return render_template("orders/cost_form.html", order=order)


@bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@role_required("admin")
def order_delete(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    before_order = row_snapshot(order, ORDER_LOG_FIELDS + COST_LOG_FIELDS)
    delete_order(order_id)
    create_operation_log(
        current_username(),
        "删除订单",
        order["order_no"],
        before_content=before_order,
    )
    flash("订单已删除。", "success")
    return redirect(url_for("main.orders"))


@bp.route("/orders/<int:order_id>/status/next", methods=["POST"])
@role_required("admin", "sales", "production", "finance")
def order_next_status(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)

    return_to = request.form.get("return_to")
    submitted_status = request.form.get("current_status")
    if submitted_status and submitted_status != order["status"]:
        flash("订单状态已被其他人更新，请刷新页面。", "error")
        return redirect(shipping_return_url(order_id, return_to))

    next_status = next_order_status(order["status"])
    if not next_status:
        flash("当前订单状态没有下一步。", "error")
    elif not can_advance_status(order["status"], next_status):
        flash("无权限推进当前状态。", "error")
    else:
        if update_order_status_if_current(order_id, order["status"], next_status):
            if next_status == "已发货":
                ensure_order_shipped_at(order_id)
            create_operation_log(
                current_username(),
                "状态下一步",
                order["order_no"],
                before_content={"status": order["status"]},
                after_content={"status": next_status},
            )
            flash(f"订单状态已更新为：{next_status}。", "success")
            if next_status == "已发货":
                return redirect(url_for("main.order_shipping_update", order_id=order_id, return_to=return_to or "detail"))
        else:
            flash("订单状态已被其他人更新，请刷新页面。", "error")

    return redirect(shipping_return_url(order_id, return_to))


@bp.route("/orders/<int:order_id>/shipping", methods=["GET", "POST"])
@role_required("admin", "sales", "production")
def order_shipping_update(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)

    return_to = request.values.get("return_to")
    if request.method == "GET":
        return render_template(
            "orders/shipping_form.html",
            order=order,
            shipping_companies=SHIPPING_COMPANIES,
            return_to=return_to,
            cancel_url=shipping_return_url(order_id, return_to),
        )

    before_shipping = row_snapshot(
        order,
        ["shipping_company", "tracking_number", "shipping_freight", "shipped_at", "shipping_note"],
    )
    shipped_at = request.form.get("shipped_at", "").strip() or order_field(order, "shipped_at") or now_text()
    data = {
        "shipping_company": request.form.get("shipping_company", "").strip(),
        "tracking_number": request.form.get("tracking_number", "").strip(),
        "shipping_freight": to_float(request.form.get("shipping_freight")),
        "shipped_at": shipped_at,
        "shipping_note": request.form.get("shipping_note", "").strip(),
    }
    update_order_shipping(order_id, data)
    create_operation_log(
        current_username(),
        "填写快递信息",
        order["order_no"],
        before_content=before_shipping,
        after_content=data,
    )
    flash("快递信息已保存。", "success")
    return redirect(shipping_return_url(order_id, return_to))


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@role_required("admin", "sales")
def order_cancel(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    if not can_cancel_order():
        abort(403)

    submitted_status = request.form.get("current_status")
    if submitted_status and submitted_status != order["status"]:
        flash("订单状态已被其他人更新，请刷新页面。", "error")
    elif update_order_status_if_current(order_id, order["status"], "已取消"):
        create_operation_log(
            current_username(),
            "取消订单",
            order["order_no"],
            before_content={"status": order["status"]},
            after_content={"status": "已取消"},
        )
        flash("订单状态已更新为：已取消。", "success")
    else:
        flash("订单状态已被其他人更新，请刷新页面。", "error")

    if request.form.get("return_to") == "list":
        return redirect(url_for("main.orders"))
    return redirect(url_for("main.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/production")
@role_required("admin", "production")
def production_sheet(order_id):
    order = get_order(order_id)
    if not order:
        abort(404)
    return render_template("orders/production.html", order=order)


@bp.route("/uploads/<path:filename>")
@login_required
def download_upload(filename):
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    extension = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    force_download = extension in {"dxf", "dwg", "zip"}
    return send_from_directory(upload_folder, filename, as_attachment=force_download)


@bp.route("/prices", methods=["GET", "POST"])
@role_required("admin")
def prices():
    if request.method == "POST":
        data = {
            "specification": request.form.get("specification", "").strip(),
            "thickness": request.form.get("thickness", "").strip(),
            "sale_price": to_float(request.form.get("sale_price")),
            "cost_price": to_float(request.form.get("cost_price")),
            "current_stock": to_float(request.form.get("current_stock")),
            "safety_stock": to_float(request.form.get("safety_stock")),
        }
        if data["specification"] and data["thickness"]:
            create_price_item(data)
            create_operation_log(
                current_username(),
                "修改价格表",
                after_content=data_snapshot(data, PRICE_LOG_FIELDS),
            )
            flash("价格已新增。", "success")
            return redirect(url_for("main.prices"))
        flash("规格和厚度必须填写。", "error")

    return render_template("prices.html", prices=list_price_items())


@bp.route("/prices/<int:item_id>/edit", methods=["POST"])
@role_required("admin")
def price_edit(item_id):
    item = get_db().execute("SELECT * FROM price_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    data = {
        "specification": request.form.get("specification", "").strip(),
        "thickness": request.form.get("thickness", "").strip(),
        "sale_price": to_float(request.form.get("sale_price")),
        "cost_price": to_float(request.form.get("cost_price")),
        "current_stock": to_float(request.form.get("current_stock")),
        "safety_stock": to_float(request.form.get("safety_stock")),
    }
    update_price_item(item_id, data)
    create_operation_log(
        current_username(),
        "修改价格表",
        before_content=row_snapshot(item, PRICE_LOG_FIELDS),
        after_content=data_snapshot(data, PRICE_LOG_FIELDS),
    )
    flash("价格已修改。", "success")
    return redirect(url_for("main.prices"))


@bp.route("/prices/<int:item_id>/delete", methods=["POST"])
@role_required("admin")
def price_delete(item_id):
    item = get_db().execute("SELECT * FROM price_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    delete_price_item(item_id)
    create_operation_log(
        current_username(),
        "修改价格表",
        before_content=row_snapshot(item, PRICE_LOG_FIELDS),
    )
    flash("价格已删除。", "success")
    return redirect(url_for("main.prices"))


@bp.route("/purchase-list")
@login_required
def purchase_list():
    return render_template(
        "purchase_list.html",
        reminders=list_purchase_reminders(),
        print_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@bp.route("/statistics")
@role_required("admin", "finance")
def statistics():
    year = to_int(request.args.get("year"), date.today().year)
    month_number = to_int(request.args.get("month"), date.today().month)
    report = build_monthly_statistics(get_db(), year, month_number, ORDER_SOURCES, REPORT_STATUSES)
    return render_template(
        "statistics.html",
        **report,
    )


@bp.route("/operation-logs")
@role_required("admin")
def operation_logs():
    return render_template("operation_logs.html", logs=list_operation_logs())


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "sales")
        if role not in ROLE_LABELS:
            flash("角色不正确。", "error")
        elif not username or not password:
            flash("用户名和初始密码必须填写。", "error")
        else:
            try:
                create_user({"username": username, "password": password, "role": role})
                flash("用户已新增。", "success")
                return redirect(url_for("main.users"))
            except Exception:
                flash("用户名已存在，请换一个用户名。", "error")

    return render_template("users.html", users=list_users(), roles=ROLE_LABELS)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@role_required("admin")
def user_role(user_id):
    role = request.form.get("role")
    if role not in ROLE_LABELS:
        flash("角色不正确。", "error")
    else:
        update_user_role(user_id, role)
        flash("用户角色已更新。", "success")
    return redirect(url_for("main.users"))


@bp.route("/users/<int:user_id>/password", methods=["POST"])
@role_required("admin")
def user_password(user_id):
    password = request.form.get("password", "")
    if not password:
        flash("新密码不能为空。", "error")
    else:
        update_user_password(user_id, password)
        flash("用户密码已更新。", "success")
    return redirect(url_for("main.users"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@role_required("admin")
def user_toggle(user_id):
    if session.get("user_id") == user_id:
        flash("不能停用当前登录账号。", "error")
        return redirect(url_for("main.users"))
    update_user_active(user_id, request.form.get("is_active") == "1")
    flash("用户启用状态已更新。", "success")
    return redirect(url_for("main.users"))


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@role_required("admin")
def user_delete(user_id):
    if session.get("user_id") == user_id:
        flash("不能删除当前登录账号。", "error")
        return redirect(url_for("main.users"))
    delete_user(user_id)
    flash("用户已删除。", "success")
    return redirect(url_for("main.users"))
