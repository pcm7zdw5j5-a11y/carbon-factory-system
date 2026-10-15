import os
import secrets

from flask import Flask, g, redirect, render_template, request, url_for

from .auth import (
    can_advance_status,
    can_cancel_order,
    can_create_order,
    can_delete_order,
    can_edit_cost,
    can_edit_order,
    can_edit_shipping,
    can_manage_prices,
    can_manage_users,
    can_view_cost_profit,
    can_view_production_sheet,
    can_view_quote,
    can_view_statistics,
    load_logged_in_user,
)
from .database import init_db
from .filters import register_filters
from .services.profit_alerts import order_profit_alert


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        INITIAL_ADMIN_PASSWORD=os.environ.get("INITIAL_ADMIN_PASSWORD"),
        DATABASE=os.environ.get("DATABASE", "carbon_factory.db"),
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", "uploads"),
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,
    )

    if test_config:
        app.config.update(test_config)

    if app.config.get("TESTING") and not app.config.get("INITIAL_ADMIN_PASSWORD"):
        app.config["INITIAL_ADMIN_PASSWORD"] = "admin123"
    if not app.config.get("TESTING"):
        if app.config["SECRET_KEY"] in {
            "carbon-factory-local-secret",
            "please-change-this-to-a-long-random-string",
        }:
            raise RuntimeError("Set a unique SECRET_KEY before starting the application")

    if not os.path.isabs(app.config["UPLOAD_FOLDER"]):
        app.config["UPLOAD_FOLDER"] = os.path.abspath(
            os.path.join(app.root_path, "..", app.config["UPLOAD_FOLDER"])
        )
    if not os.path.isabs(app.config["DATABASE"]):
        app.config["DATABASE"] = os.path.abspath(
            os.path.join(app.root_path, "..", app.config["DATABASE"])
        )

    register_filters(app)

    from .routes import bp

    app.register_blueprint(bp)

    @app.before_request
    def protect_pages():
        load_logged_in_user()
        if request.endpoint in {"main.login", "static"} or request.endpoint is None:
            return None
        if g.current_user is None:
            return redirect(url_for("main.login", next=request.full_path))
        return None

    @app.after_request
    def prevent_back_button_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.context_processor
    def inject_auth_helpers():
        return {
            "current_user": g.get("current_user"),
            "can_advance_status": can_advance_status,
            "can_cancel_order": can_cancel_order,
            "can_create_order": can_create_order,
            "can_delete_order": can_delete_order,
            "can_edit_cost": can_edit_cost,
            "can_edit_order": can_edit_order,
            "can_edit_shipping": can_edit_shipping,
            "can_manage_prices": can_manage_prices,
            "can_manage_users": can_manage_users,
            "can_view_cost_profit": can_view_cost_profit,
            "can_view_production_sheet": can_view_production_sheet,
            "can_view_quote": can_view_quote,
            "can_view_statistics": can_view_statistics,
            "can_use_board_calculator": lambda: bool(g.get("current_user") and g.current_user["role"] in {"admin", "sales", "production"}),
            "order_profit_alert": order_profit_alert,
        }

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    with app.app_context():
        init_db()

    return app


# WSGI entrypoint for deployment tools such as:
# gunicorn app:app
app = create_app()
