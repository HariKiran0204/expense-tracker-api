from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db, bcrypt
from app.models import User
from app.utils.responses import success_response, error_response
from app.utils.validators import validate_email, validate_password

users_bp = Blueprint("users", __name__, url_prefix="/api/users")


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


@users_bp.route("/me", methods=["GET"])
@jwt_required()
def get_profile():
    """
    Get current user's profile
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    responses:
      200:
        description: User profile returned
      401:
        description: Unauthorized
    """
    user = _get_current_user()
    return success_response(user.to_dict())


@users_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_profile():
    """
    Update profile (name and/or email)
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              name:
                type: string
              email:
                type: string
    responses:
      200:
        description: Profile updated
      400:
        description: Validation error
    """
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    errors = {}

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            errors["name"] = "Name cannot be empty."
        else:
            user.name = name

    if "email" in data:
        email = (data["email"] or "").strip().lower()
        if not validate_email(email):
            errors["email"] = "Invalid email format."
        elif User.query.filter(User.email == email, User.id != user.id).first():
            errors["email"] = "Email already in use."
        else:
            user.email = email

    if errors:
        return error_response("Validation failed", 400, errors)

    db.session.commit()
    return success_response(user.to_dict(), "Profile updated")


@users_bp.route("/me/password", methods=["PUT"])
@jwt_required()
def change_password():
    """
    Change password
    ---
    tags:
      - Users
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [current_password, new_password]
            properties:
              current_password:
                type: string
              new_password:
                type: string
    responses:
      200:
        description: Password changed
      400:
        description: Validation error or wrong current password
    """
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    errors = {}

    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password:
        errors["current_password"] = "Current password is required."
    elif not bcrypt.check_password_hash(user.password_hash, current_password):
        errors["current_password"] = "Current password is incorrect."

    if not new_password:
        errors["new_password"] = "New password is required."
    else:
        pwd_errors = validate_password(new_password)
        if pwd_errors:
            errors["new_password"] = pwd_errors[0]

    if errors:
        return error_response("Validation failed", 400, errors)

    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    db.session.commit()
    return success_response(message="Password changed successfully")
