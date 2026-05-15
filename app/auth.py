from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from .database import get_db


ROLE_LABELS = {
    "admin": "管理员",
    "sales": "销售/客服",
    "production": "生产/板房",
    "finance": "财务",
}

SALES_TRANSITIONS = {
    ("待审核", "待报价"),
    ("待报价", "已报价"),
    ("已报价", "已付款"),
}

PRODUCTION_TRANSITIONS = {
    ("已付款", "待下板"),
    ("待下板", "加工中"),
    ("加工中", "待质检"),
    ("待质检", "待包装"),
    ("待包装", "待发货"),
    ("待发货", "已发货"),
    ("已发货", "已完成"),
}


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def load_logged_in_user():
    user_id = session.get("user_id")
    g.current_user = get_user(user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.get("current_user") is None:
            return redirect(url_for("main.login", next=request.full_path))
        return view(**kwargs)

    return wrapped_view


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            user = g.get("current_user")
            if user is None:
                return redirect(url_for("main.login", next=request.full_path))
            if user["role"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def current_role():
    user = g.get("current_user")
    return user["role"] if user else None


def has_role(*roles):
    role = current_role()
    return role in roles


def can_manage_users():
    return has_role("admin")


def can_create_order():
    return has_role("admin", "sales")


def can_edit_order():
    return has_role("admin", "sales")


def can_delete_order():
    return has_role("admin")


def can_cancel_order():
    return has_role("admin", "sales")


def can_view_quote():
    return has_role("admin", "sales", "finance")


def can_view_cost_profit():
    return has_role("admin", "finance")


def can_view_statistics():
    return has_role("admin", "finance")


def can_manage_prices():
    return has_role("admin")


def can_view_production_sheet():
    return has_role("admin", "production")


def can_edit_cost():
    return has_role("admin", "finance")


def can_edit_shipping():
    return has_role("admin", "sales", "production")


def can_advance_status(old_status, new_status):
    if not new_status:
        return False
    role = current_role()
    if role == "admin":
        return True
    if role == "sales":
        return (old_status, new_status) in SALES_TRANSITIONS
    if role == "production":
        return (old_status, new_status) in PRODUCTION_TRANSITIONS
    return False


def dashboard_focus_statuses():
    role = current_role()
    if role == "sales":
        return ["待报价", "已报价", "已付款"]
    if role == "production":
        return ["待下板", "加工中", "待质检"]
    return []
