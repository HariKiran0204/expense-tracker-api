from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from app import db
from app.models import Transaction, Category
from app.utils.responses import success_response, error_response
from app.utils.validators import validate_transaction_type, validate_date, validate_positive_number

transactions_bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")


def _get_user_id():
    return int(get_jwt_identity())


def _check_category(category_id, user_id):
    """Return category if accessible to user, else None."""
    return Category.query.filter(
        Category.id == category_id,
        or_(Category.is_default == True, Category.user_id == user_id)
    ).first()


@transactions_bp.route("", methods=["GET"])
@jwt_required()
def list_transactions():
    """
    List transactions with filtering, sorting, and pagination
    ---
    tags:
      - Transactions
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: type
        schema:
          type: string
          enum: [expense, income]
        description: Filter by type
      - in: query
        name: category_id
        schema:
          type: integer
        description: Filter by category
      - in: query
        name: start_date
        schema:
          type: string
          format: date
          example: "2024-01-01"
        description: Start of date range (inclusive)
      - in: query
        name: end_date
        schema:
          type: string
          format: date
          example: "2024-12-31"
        description: End of date range (inclusive)
      - in: query
        name: sort_by
        schema:
          type: string
          enum: [date, amount]
          default: date
      - in: query
        name: order
        schema:
          type: string
          enum: [asc, desc]
          default: desc
      - in: query
        name: page
        schema:
          type: integer
          default: 1
      - in: query
        name: per_page
        schema:
          type: integer
          default: 20
    responses:
      200:
        description: Paginated list of transactions
    """
    user_id = _get_user_id()
    query = Transaction.query.filter_by(user_id=user_id)

    # Filters
    t_type = request.args.get("type")
    if t_type:
        if not validate_transaction_type(t_type):
            return error_response("type must be 'expense' or 'income'", 400)
        query = query.filter_by(type=t_type)

    category_id = request.args.get("category_id")
    if category_id:
        try:
            query = query.filter_by(category_id=int(category_id))
        except ValueError:
            return error_response("category_id must be an integer", 400)

    start_date = request.args.get("start_date")
    if start_date:
        d = validate_date(start_date)
        if not d:
            return error_response("start_date must be YYYY-MM-DD", 400)
        query = query.filter(Transaction.date >= d)

    end_date = request.args.get("end_date")
    if end_date:
        d = validate_date(end_date)
        if not d:
            return error_response("end_date must be YYYY-MM-DD", 400)
        query = query.filter(Transaction.date <= d)

    # Sorting
    sort_by = request.args.get("sort_by", "date")
    order = request.args.get("order", "desc")
    if sort_by not in ("date", "amount"):
        return error_response("sort_by must be 'date' or 'amount'", 400)
    if order not in ("asc", "desc"):
        return error_response("order must be 'asc' or 'desc'", 400)

    sort_col = Transaction.date if sort_by == "date" else Transaction.amount
    query = query.order_by(sort_col.asc() if order == "asc" else sort_col.desc())

    # Pagination
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        return error_response("page and per_page must be integers", 400)

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response(
        [t.to_dict() for t in paginated.items],
        meta={
            "page": page,
            "per_page": per_page,
            "total": paginated.total,
            "pages": paginated.pages,
            "has_next": paginated.has_next,
            "has_prev": paginated.has_prev,
        },
    )


@transactions_bp.route("/<int:transaction_id>", methods=["GET"])
@jwt_required()
def get_transaction(transaction_id):
    """
    Get a single transaction by ID
    ---
    tags:
      - Transactions
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transaction_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Transaction data
      404:
        description: Not found
    """
    user_id = _get_user_id()
    txn = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
    if not txn:
        return error_response("Transaction not found", 404)
    return success_response(txn.to_dict())


@transactions_bp.route("", methods=["POST"])
@jwt_required()
def create_transaction():
    """
    Create a new transaction
    ---
    tags:
      - Transactions
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [type, amount, category_id, date]
            properties:
              type:
                type: string
                enum: [expense, income]
              amount:
                type: number
                example: 49.99
              category_id:
                type: integer
              date:
                type: string
                format: date
                example: "2024-06-01"
              note:
                type: string
    responses:
      201:
        description: Transaction created
      400:
        description: Validation error
    """
    user_id = _get_user_id()
    data = request.get_json(silent=True) or {}
    errors = {}

    t_type = (data.get("type") or "").strip()
    if not t_type:
        errors["type"] = "Type is required."
    elif not validate_transaction_type(t_type):
        errors["type"] = "Type must be 'expense' or 'income'."

    amount = data.get("amount")
    if amount is None:
        errors["amount"] = "Amount is required."
    elif not validate_positive_number(amount):
        errors["amount"] = "Amount must be a positive number."

    category_id = data.get("category_id")
    if category_id is None:
        errors["category_id"] = "Category is required."

    date_str = data.get("date")
    txn_date = None
    if not date_str:
        errors["date"] = "Date is required."
    else:
        txn_date = validate_date(date_str)
        if not txn_date:
            errors["date"] = "Date must be in YYYY-MM-DD format."

    if errors:
        return error_response("Validation failed", 400, errors)

    category = _check_category(int(category_id), user_id)
    if not category:
        return error_response("Category not found or not accessible", 404)

    txn = Transaction(
        user_id=user_id,
        type=t_type,
        amount=round(float(amount), 2),
        category_id=category.id,
        date=txn_date,
        note=(data.get("note") or "").strip() or None,
    )
    db.session.add(txn)
    db.session.commit()
    return success_response(txn.to_dict(), "Transaction created", 201)


@transactions_bp.route("/<int:transaction_id>", methods=["PUT"])
@jwt_required()
def update_transaction(transaction_id):
    """
    Update a transaction
    ---
    tags:
      - Transactions
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transaction_id
        required: true
        schema:
          type: integer
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            properties:
              type:
                type: string
                enum: [expense, income]
              amount:
                type: number
              category_id:
                type: integer
              date:
                type: string
                format: date
              note:
                type: string
    responses:
      200:
        description: Transaction updated
      404:
        description: Not found
    """
    user_id = _get_user_id()
    txn = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
    if not txn:
        return error_response("Transaction not found", 404)

    data = request.get_json(silent=True) or {}
    errors = {}

    if "type" in data:
        if not validate_transaction_type(data["type"]):
            errors["type"] = "Type must be 'expense' or 'income'."
        else:
            txn.type = data["type"]

    if "amount" in data:
        if not validate_positive_number(data["amount"]):
            errors["amount"] = "Amount must be a positive number."
        else:
            txn.amount = round(float(data["amount"]), 2)

    if "category_id" in data:
        cat = _check_category(int(data["category_id"]), user_id)
        if not cat:
            errors["category_id"] = "Category not found or not accessible."
        else:
            txn.category_id = cat.id

    if "date" in data:
        d = validate_date(data["date"])
        if not d:
            errors["date"] = "Date must be in YYYY-MM-DD format."
        else:
            txn.date = d

    if "note" in data:
        txn.note = (data["note"] or "").strip() or None

    if errors:
        return error_response("Validation failed", 400, errors)

    db.session.commit()
    return success_response(txn.to_dict(), "Transaction updated")


@transactions_bp.route("/<int:transaction_id>", methods=["DELETE"])
@jwt_required()
def delete_transaction(transaction_id):
    """
    Delete a transaction
    ---
    tags:
      - Transactions
    security:
      - BearerAuth: []
    parameters:
      - in: path
        name: transaction_id
        required: true
        schema:
          type: integer
    responses:
      200:
        description: Deleted
      404:
        description: Not found
    """
    user_id = _get_user_id()
    txn = Transaction.query.filter_by(id=transaction_id, user_id=user_id).first()
    if not txn:
        return error_response("Transaction not found", 404)

    db.session.delete(txn)
    db.session.commit()
    return success_response(message="Transaction deleted")
