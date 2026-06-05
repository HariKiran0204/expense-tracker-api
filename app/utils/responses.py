from flask import jsonify


def success_response(data=None, message="Success", status_code=200, meta=None):
    payload = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status_code


def error_response(message="An error occurred", status_code=400, errors=None):
    payload = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status_code


def register_error_handlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return error_response("Bad request", 400)

    @app.errorhandler(401)
    def unauthorized(e):
        return error_response("Unauthorized", 401)

    @app.errorhandler(403)
    def forbidden(e):
        return error_response("Forbidden", 403)

    @app.errorhandler(404)
    def not_found(e):
        return error_response("Resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response("Method not allowed", 405)

    @app.errorhandler(429)
    def ratelimit_exceeded(e):
        return error_response("Too many requests. Please slow down.", 429)

    @app.errorhandler(500)
    def internal_error(e):
        return error_response("Internal server error", 500)
