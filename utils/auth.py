from functools import wraps
from flask import session, jsonify, redirect, url_for, request


def require_role(*allowed_roles):
    """
    Decorator factory.
    - If allowed_roles is empty: requires authenticated user (any role).
    - If allowed_roles provided: requires session role to be in allowed_roles.
    Works for both API and page routes (returns JSON 401/403 for API paths).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login'))
            if allowed_roles and session.get('role') not in allowed_roles:
                return jsonify({'error': 'Access required'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
