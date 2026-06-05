from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
import logging

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)

    # JWT blocklist check
    from app.models import TokenBlocklist

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        return db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar() is not None

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        from app.utils.responses import error_response
        return error_response("Token has expired", 401)

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        from app.utils.responses import error_response
        return error_response("Invalid token", 401)

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        from app.utils.responses import error_response
        return error_response("Authorization token is required", 401)

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        from app.utils.responses import error_response
        return error_response("Token has been revoked", 401)

    # Swagger
    swagger_config = {
        "headers": [],
        "specs": [{"endpoint": "apispec", "route": "/apispec.json", "rule_filter": lambda rule: True, "model_filter": lambda tag: True}],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs",
    }
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Expense Tracker API",
            "description": "A secure REST API for personal expense tracking with JWT authentication.",
            "version": "1.0.0",
            "contact": {"email": "dev@example.com"},
        },
        "securityDefinitions": {
            "BearerAuth": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Enter: **Bearer &lt;your_token&gt;**",
            }
        },
        "basePath": "/",
        "schemes": ["http", "https"],
    }
    Swagger(app, config=swagger_config, template=swagger_template)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.users import users_bp
    from app.routes.categories import categories_bp
    from app.routes.transactions import transactions_bp
    from app.routes.analytics import analytics_bp

    # Apply rate limiting to auth endpoints
    limiter.limit("10 per minute")(auth_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(analytics_bp)

    # Request logging
    @app.after_request
    def log_request(response):
        from flask import request
        app.logger.info(f"{request.method} {request.path} → {response.status_code}")
        return response

    # Error handlers
    from app.utils.responses import register_error_handlers
    register_error_handlers(app)

    # Create tables
    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    """Seed default categories if not present."""
    from app.models import Category
    defaults = ["Food", "Transport", "Bills", "Health", "Shopping", "Travel", "Leisure", "Other"]
    for name in defaults:
        if not Category.query.filter_by(name=name, is_default=True).first():
            db.session.add(Category(name=name, is_default=True, user_id=None))
    db.session.commit()
