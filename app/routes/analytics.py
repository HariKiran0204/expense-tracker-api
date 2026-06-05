from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, extract
from datetime import date, timedelta
from calendar import monthrange
from app import db
from app.models import Transaction, Category
from app.utils.responses import success_response, error_response
from app.utils.validators import validate_date

analytics_bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


def _get_user_id():
    return int(get_jwt_identity())


def _parse_period(args):
    """Parse start_date/end_date query params; default to current month."""
    start_str = args.get("start_date")
    end_str = args.get("end_date")
    today = date.today()

    if start_str:
        start = validate_date(start_str)
        if not start:
            return None, None, "start_date must be YYYY-MM-DD"
    else:
        start = today.replace(day=1)

    if end_str:
        end = validate_date(end_str)
        if not end:
            return None, None, "end_date must be YYYY-MM-DD"
    else:
        end = today

    if start > end:
        return None, None, "start_date must be before or equal to end_date"

    return start, end, None


@analytics_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    """
    Total income, total expenses, and net balance for a period
    ---
    tags:
      - Analytics
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: start_date
        schema:
          type: string
          format: date
          example: "2024-01-01"
      - in: query
        name: end_date
        schema:
          type: string
          format: date
          example: "2024-12-31"
    responses:
      200:
        description: Summary of income, expenses, and net
    """
    user_id = _get_user_id()
    start, end, err = _parse_period(request.args)
    if err:
        return error_response(err, 400)

    rows = db.session.query(
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start,
        Transaction.date <= end,
    ).group_by(Transaction.type).all()

    totals = {"income": 0.0, "expense": 0.0}
    for row in rows:
        totals[row.type] = float(row.total)

    return success_response({
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "total_income": totals["income"],
        "total_expenses": totals["expense"],
        "net_balance": round(totals["income"] - totals["expense"], 2),
    })


@analytics_bp.route("/breakdown", methods=["GET"])
@jwt_required()
def breakdown():
    """
    Spending breakdown by category for a period
    ---
    tags:
      - Analytics
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: start_date
        schema:
          type: string
          format: date
      - in: query
        name: end_date
        schema:
          type: string
          format: date
      - in: query
        name: type
        schema:
          type: string
          enum: [expense, income]
          default: expense
    responses:
      200:
        description: Category breakdown with amounts and percentages
    """
    user_id = _get_user_id()
    start, end, err = _parse_period(request.args)
    if err:
        return error_response(err, 400)

    t_type = request.args.get("type", "expense")
    if t_type not in ("expense", "income"):
        return error_response("type must be 'expense' or 'income'", 400)

    rows = db.session.query(
        Category.id,
        Category.name,
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).join(Transaction, Transaction.category_id == Category.id) \
     .filter(
        Transaction.user_id == user_id,
        Transaction.type == t_type,
        Transaction.date >= start,
        Transaction.date <= end,
    ).group_by(Category.id, Category.name).all()

    grand_total = sum(float(r.total) for r in rows)
    categories = [
        {
            "category_id": r.id,
            "category_name": r.name,
            "amount": float(r.total),
            "percentage": round((float(r.total) / grand_total) * 100, 2) if grand_total else 0,
        }
        for r in sorted(rows, key=lambda r: float(r.total), reverse=True)
    ]

    return success_response({
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "type": t_type,
        "total": grand_total,
        "categories": categories,
    })


@analytics_bp.route("/monthly", methods=["GET"])
@jwt_required()
def monthly():
    """
    Month-over-month income and expense summary
    ---
    tags:
      - Analytics
    security:
      - BearerAuth: []
    parameters:
      - in: query
        name: months
        schema:
          type: integer
          default: 6
          minimum: 1
          maximum: 24
        description: Number of past months to include
    responses:
      200:
        description: Monthly income and expense totals
    """
    user_id = _get_user_id()
    try:
        months = min(24, max(1, int(request.args.get("months", 6))))
    except ValueError:
        return error_response("months must be an integer", 400)

    today = date.today()
    # Build list of (year, month) tuples going back `months` months
    periods = []
    for i in range(months - 1, -1, -1):
        m = (today.month - 1 - i) % 12 + 1
        y = today.year + ((today.month - 1 - i) // 12)
        periods.append((y, m))

    # One query for all data in range
    start_date = date(periods[0][0], periods[0][1], 1)
    end_month = periods[-1]
    end_date = date(end_month[0], end_month[1], monthrange(end_month[0], end_month[1])[1])

    rows = db.session.query(
        extract("year", Transaction.date).label("year"),
        extract("month", Transaction.date).label("month"),
        Transaction.type,
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date,
    ).group_by("year", "month", Transaction.type).all()

    # Build a lookup dict
    lookup = {}
    for row in rows:
        key = (int(row.year), int(row.month))
        if key not in lookup:
            lookup[key] = {"income": 0.0, "expense": 0.0}
        lookup[key][row.type] = float(row.total)

    result = []
    for y, m in periods:
        data = lookup.get((y, m), {"income": 0.0, "expense": 0.0})
        result.append({
            "year": y,
            "month": m,
            "month_label": date(y, m, 1).strftime("%B %Y"),
            "income": data["income"],
            "expenses": data["expense"],
            "net": round(data["income"] - data["expense"], 2),
        })

    return success_response({"months": months, "data": result})
