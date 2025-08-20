from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('api_key') or not session.get('server'):
            flash("برای دسترسی به این صفحه باید ابتدا لاگین کنید.", "warning")
            return redirect(url_for('login.login'))
        return f(*args, **kwargs)
    return decorated_function
