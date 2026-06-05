from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import Category
from app.utils.responses import success_response, error_response

categories_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def _get_user_id():
    return int(get_jwt_identity())


@categories_bp.route("", methods=["GET"])
@jwt_required()
def list_categories():
    """
    List all categories (default + user's custom)
    ---
    tags:
      - Categories
    security:
      - BearerAuth: []
    responses:
      200:
        description: List of categories
    """
    user_id = _get_user_id()
    cats = Category.query.filter(
        (Category.is_default == True) | (Category.user_id == user_id)
    ).all()
    return success_response([c.to_dict() for c in cats])


@categories_bp.route("", methods=["POST"])
@jwt_required()
def create_category():
    """
    Create a custom category
    ---
    tags:
      - Categories
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [name]
            properties:
              name:
                type: string
                example: Gym
    responses:
      201:
        description: Category created
      400:
        description: Validation error or duplicate name
    """
    user_id = _get_user_id()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    if not name:
        return error_response("Validation failed", 400, {"name": "Name is required."})

    exists = Category.query.filter(
        (Category.name.ilike(name)) &
        ((Category.is_default == True) | (Category.user_id == user_id))
    ).first()
    if exists:
        return error_response("Category with this name already exists", 400)

    cat = Category(name=name, is_default=False, user_id=user_id)
    db.session.add(cat)
    db.session.commit()
    return success_response(cat.to_dict(), "Category created", 201)


@categories_bp.route("/<int:category_id>", methods=["PUT"])
@jwt_required()
def update_category(category_id):
    """
    Update a custom category
    ---
    tags:
      - Categories
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: category_id
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [name]
            properties:
              name:
                type: string
    responses:
      200:
        description: Category updated
      403:
        description: Cannot modify default category or another user's category
      404:
        description: Category not found
    """
    user_id = _get_user_id()
    cat = Category.query.get(category_id)

    if not cat:
        return error_response("Category not found", 404)
    if cat.is_default:
        return error_response("Default categories cannot be modified", 403)
    if cat.user_id != user_id:
        return error_response("Forbidden", 403)

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("Validation failed", 400, {"name": "Name is required."})

    cat.name = name
    db.session.commit()
    return success_response(cat.to_dict(), "Category updated")


@categories_bp.route("/<int:category_id>", methods=["DELETE"])
@jwt_required()
def delete_category(category_id):
    """
    Delete a custom category
    ---
    tags:
      - Categories
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: category_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Category deleted
      403:
        description: Cannot delete default category or another user's category
      404:
        description: Category not found
    """
    user_id = _get_user_id()
    cat = Category.query.get(category_id)

    if not cat:
        return error_response("Category not found", 404)
    if cat.is_default:
        return error_response("Default categories cannot be deleted", 403)
    if cat.user_id != user_id:
        return error_response("Forbidden", 403)

    db.session.delete(cat)
    db.session.commit()
    return success_response(message="Category deleted")
