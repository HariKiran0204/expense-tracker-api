from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from app import db, bcrypt
from app.models import User, TokenBlocklist
from app.utils.responses import success_response, error_response
from app.utils.validators import validate_email, validate_password

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new user
    ---
    tags:
      - Auth
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [name, email, password]
            properties:
              name:
                type: string
                example: John Doe
              email:
                type: string
                example: john@example.com
              password:
                type: string
                example: secret123
    responses:
      201:
        description: User registered successfully
      400:
        description: Validation error or email already exists
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response("Request body must be JSON", 400)

    errors = {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name:
        errors["name"] = "Name is required."
    if not email:
        errors["email"] = "Email is required."
    elif not validate_email(email):
        errors["email"] = "Invalid email format."
    if not password:
        errors["password"] = "Password is required."
    else:
        pwd_errors = validate_password(password)
        if pwd_errors:
            errors["password"] = pwd_errors[0]

    if errors:
        return error_response("Validation failed", 400, errors)

    if User.query.filter_by(email=email).first():
        return error_response("Email already registered", 400)

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(name=name, email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return success_response(
        {"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token},
        "User registered successfully",
        201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login and receive tokens
    ---
    tags:
      - Auth
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [email, password]
            properties:
              email:
                type: string
                example: john@example.com
              password:
                type: string
                example: secret123
    responses:
      200:
        description: Login successful
      401:
        description: Invalid credentials
    """
    data = request.get_json(silent=True)
    if not data:
        return error_response("Request body must be JSON", 400)

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return error_response("Email and password are required", 400)

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return error_response("Invalid email or password", 401)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return success_response(
        {"user": user.to_dict(), "access_token": access_token, "refresh_token": refresh_token},
        "Login successful",
    )


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token
    ---
    tags:
      - Auth
    security:
      - BearerAuth: []
    responses:
      200:
        description: New access token issued
      401:
        description: Invalid or expired refresh token
    """
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return success_response({"access_token": access_token}, "Token refreshed")


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """
    Logout — revoke current access token
    ---
    tags:
      - Auth
    security:
      - BearerAuth: []
    responses:
      200:
        description: Logged out successfully
    """
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()
    return success_response(message="Logged out successfully")
