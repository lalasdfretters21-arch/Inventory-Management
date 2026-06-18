from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import glob
from datetime import datetime
from functools import wraps

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'inventory-dev-secret-change-in-production')
CORS(app, supports_credentials=True)

DATABASE = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'inventory.db'))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'admin',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        model TEXT,
        specs TEXT,
        date_acquired DATE,
        amount REAL,
        rv_number TEXT UNIQUE,
        po_number TEXT,
        acquired_by TEXT,
        location_installed TEXT,
        remarks TEXT,
        date_entry DATETIME DEFAULT CURRENT_TIMESTAMP,
        entry_by TEXT,
        user_id INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Migrate existing databases
    c.execute("PRAGMA table_info(inventory)")
    columns = {row[1] for row in c.fetchall()}
    if 'user_id' not in columns:
        c.execute('ALTER TABLE inventory ADD COLUMN user_id INTEGER')

    c.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in c.fetchall()}
    if 'profile_pic' not in user_columns:
        c.execute('ALTER TABLE users ADD COLUMN profile_pic TEXT')

    c.execute(
        "SELECT id FROM users WHERE username = 'admin' AND full_name = 'System Administrator'"
    )
    default_admin = c.fetchone()
    if default_admin:
        c.execute('UPDATE inventory SET user_id = NULL WHERE user_id = ?', (default_admin['id'],))
        c.execute('DELETE FROM users WHERE id = ?', (default_admin['id'],))

    conn.commit()
    conn.close()

def dict_from_row(row):
    """Convert sqlite3.Row to dictionary"""
    if row is None:
        return None
    return dict(row)

def validate_inventory_item(data):
    """Return the first missing required field label, or None if valid."""
    required = {
        'description': 'Description',
        'model': 'Model',
        'specs': 'Specifications',
        'rv_number': 'RV#',
        'po_number': 'PO#',
        'date_acquired': 'Date Acquired',
        'acquired_by': 'Acquired by',
        'location_installed': 'Location Installed',
    }

    for field, label in required.items():
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return label

    return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

def allowed_avatar_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS

def get_user_item_count(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as count FROM inventory WHERE user_id = ?', (user_id,))
    count = c.fetchone()['count']
    conn.close()
    return count

def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        '''SELECT u.id, u.username, u.full_name, u.role, u.profile_pic, u.created_at,
                  COUNT(i.id) as item_count
           FROM users u
           LEFT JOIN inventory i ON i.user_id = u.id
           WHERE u.id = ?
           GROUP BY u.id''',
        (session['user_id'],)
    )
    user = dict_from_row(c.fetchone())
    conn.close()
    return user

def delete_user_avatar(user_id):
    pattern = os.path.join(UPLOAD_FOLDER, f'user_{user_id}.*')
    for filepath in glob.glob(pattern):
        try:
            os.remove(filepath)
        except OSError:
            pass

@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/')
@login_required
def index():
    """Serve the main PWA page"""
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    """Serve the PWA manifest"""
    return app.send_static_file('manifest.json')

# ==================== AUTH ENDPOINTS ====================

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()

    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = user['role']

    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'full_name': user['full_name'],
            'role': user['role']
        }
    }), 200

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    full_name = (data.get('full_name') or '').strip()

    if not username or not password or not full_name:
        return jsonify({'error': 'Username, password, and full name are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            'INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)',
            (username, generate_password_hash(password), full_name, 'admin')
        )
        conn.commit()
        user_id = c.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 400
    finally:
        conn.close()

    session['user_id'] = user_id
    session['username'] = username
    session['full_name'] = full_name
    session['role'] = 'admin'

    return jsonify({
        'message': 'Account created successfully',
        'user': {
            'id': user_id,
            'username': username,
            'full_name': full_name,
            'role': 'admin'
        }
    }), 201

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/auth/me', methods=['GET'])
@login_required
def auth_me():
    user = get_current_user()
    if user is None:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify({'user': user}), 200

@app.route('/api/auth/me', methods=['PATCH'])
@login_required
def auth_update_profile():
    data = request.json or {}
    user_id = session['user_id']

    username = (data.get('username') or '').strip()
    full_name = (data.get('full_name') or '').strip()

    if not username or not full_name:
        return jsonify({'error': 'Username and full name are required'}), 400

    conn = get_db_connection()
    c = conn.cursor()

    c.execute('SELECT id FROM users WHERE username = ? AND id != ?', (username, user_id))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Username already taken'}), 400

    c.execute(
        'UPDATE users SET username = ?, full_name = ? WHERE id = ?',
        (username, full_name, user_id)
    )
    conn.commit()
    conn.close()

    session['username'] = username
    session['full_name'] = full_name

    user = get_current_user()
    return jsonify({'message': 'Profile updated successfully', 'user': user}), 200

@app.route('/api/auth/me/avatar', methods=['POST'])
@login_required
def auth_upload_avatar():
    user_id = session['user_id']

    if 'avatar' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['avatar']
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_avatar_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use PNG, JPG, GIF, or WebP'}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_AVATAR_SIZE:
        return jsonify({'error': 'File too large. Maximum size is 2 MB'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    delete_user_avatar(user_id)
    filename = f'user_{user_id}.{ext}'
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    profile_pic = f'/static/uploads/avatars/{filename}'
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET profile_pic = ? WHERE id = ?', (profile_pic, user_id))
    conn.commit()
    conn.close()

    user = get_current_user()
    return jsonify({'message': 'Profile picture updated', 'user': user}), 200

@app.route('/api/auth/me/avatar', methods=['DELETE'])
@login_required
def auth_remove_avatar():
    user_id = session['user_id']
    delete_user_avatar(user_id)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET profile_pic = NULL WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    user = get_current_user()
    return jsonify({'message': 'Profile picture removed', 'user': user}), 200

@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def auth_change_password():
    data = request.json or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''

    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password are required'}), 400
    if len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],))
    user = c.fetchone()
    if user is None or not check_password_hash(user['password_hash'], current_password):
        conn.close()
        return jsonify({'error': 'Current password is incorrect'}), 401

    c.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (generate_password_hash(new_password), session['user_id'])
    )
    conn.commit()
    conn.close()

    return jsonify({'message': 'Password changed successfully'}), 200

@app.route('/api/auth/me', methods=['DELETE'])
@login_required
def auth_delete_account():
    data = request.json or {}
    password = data.get('password') or ''
    user_id = session['user_id']

    if not password:
        return jsonify({'error': 'Password is required to delete your account'}), 400

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    if user is None or not check_password_hash(user['password_hash'], password):
        conn.close()
        return jsonify({'error': 'Incorrect password'}), 401

    item_count = get_user_item_count(user_id)
    if item_count > 0:
        conn.close()
        return jsonify({
            'error': f'Cannot delete account while you have {item_count} inventory item(s) listed. Remove or reassign them first.'
        }), 400

    delete_user_avatar(user_id)
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    session.clear()
    return jsonify({'message': 'Account deleted successfully'}), 200

# ==================== ADMIN ENDPOINTS ====================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """Get all users with inventory stats"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            SELECT u.id, u.username, u.full_name, u.role, u.created_at,
                   COUNT(i.id) as item_count,
                   COALESCE(SUM(i.amount), 0) as total_value
            FROM users u
            LEFT JOIN inventory i ON i.user_id = u.id
            GROUP BY u.id
            ORDER BY u.role DESC, u.full_name ASC
        ''')
        users = [dict_from_row(row) for row in c.fetchall()]
        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users/<int:user_id>/inventory', methods=['GET'])
@admin_required
def admin_get_user_inventory(user_id):
    """Get inventory items for a specific user"""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute('SELECT id, username, full_name, role FROM users WHERE id = ?', (user_id,))
        user = dict_from_row(c.fetchone())
        if user is None:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        c.execute(
            'SELECT * FROM inventory WHERE user_id = ? ORDER BY date_entry DESC',
            (user_id,)
        )
        items = [dict_from_row(row) for row in c.fetchall()]
        conn.close()

        return jsonify({'user': user, 'items': items}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== INVENTORY API ENDPOINTS ====================

@app.route('/api/inventory', methods=['GET'])
@login_required
def get_inventory():
    """Get all inventory items with optional filtering"""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        search = request.args.get('search', '')
        location = request.args.get('location', '')

        query = "SELECT * FROM inventory WHERE 1=1"
        params = []

        if search:
            query += " AND (description LIKE ? OR model LIKE ? OR rv_number LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])

        if location:
            query += " AND location_installed LIKE ?"
            params.append(f"%{location}%")

        query += " ORDER BY date_entry DESC"

        c.execute(query, params)
        items = [dict_from_row(row) for row in c.fetchall()]
        conn.close()

        return jsonify(items), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/<int:item_id>', methods=['GET'])
@login_required
def get_inventory_item(item_id):
    """Get a specific inventory item"""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
        item = dict_from_row(c.fetchone())
        conn.close()

        if item is None:
            return jsonify({'error': 'Item not found'}), 404

        return jsonify(item), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory', methods=['POST'])
@login_required
def create_inventory_item():
    """Create a new inventory item"""
    try:
        data = request.json

        missing = validate_inventory_item(data)
        if missing:
            return jsonify({'error': f'{missing} is required'}), 400

        entry_by = session.get('full_name') or session.get('username')
        user_id = session.get('user_id')

        conn = get_db_connection()
        c = conn.cursor()

        c.execute('''INSERT INTO inventory
            (description, model, specs, date_acquired, amount, rv_number,
             po_number, acquired_by, location_installed, remarks, entry_by, user_id, date_entry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                data.get('description'),
                data.get('model'),
                data.get('specs'),
                data.get('date_acquired'),
                data.get('amount'),
                data.get('rv_number'),
                data.get('po_number'),
                data.get('acquired_by'),
                data.get('location_installed'),
                data.get('remarks'),
                entry_by,
                user_id,
                data.get('date_entry') or datetime.now().isoformat()
            )
        )

        conn.commit()
        item_id = c.lastrowid
        conn.close()

        return jsonify({'id': item_id, 'message': 'Item created successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'RV# already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
@login_required
def update_inventory_item(item_id):
    """Update an inventory item"""
    try:
        data = request.json

        missing = validate_inventory_item(data)
        if missing:
            return jsonify({'error': f'{missing} is required'}), 400

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT id FROM inventory WHERE id = ?", (item_id,))
        if c.fetchone() is None:
            conn.close()
            return jsonify({'error': 'Item not found'}), 404

        update_fields = []
        params = []

        for field in ['description', 'model', 'specs', 'date_acquired', 'amount',
                      'rv_number', 'po_number', 'acquired_by', 'location_installed',
                      'remarks']:
            if field in data:
                update_fields.append(f"{field} = ?")
                params.append(data[field])

        if not update_fields:
            conn.close()
            return jsonify({'error': 'No fields to update'}), 400

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(item_id)

        query = f"UPDATE inventory SET {', '.join(update_fields)} WHERE id = ?"
        c.execute(query, params)
        conn.commit()
        conn.close()

        return jsonify({'message': 'Item updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
@login_required
def delete_inventory_item(item_id):
    """Delete an inventory item"""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT id FROM inventory WHERE id = ?", (item_id,))
        if c.fetchone() is None:
            conn.close()
            return jsonify({'error': 'Item not found'}), 404

        c.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Item deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory/export/csv', methods=['GET'])
@login_required
def export_csv():
    """Export inventory to CSV"""
    try:
        import csv
        from io import StringIO

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM inventory ORDER BY date_entry DESC")
        rows = c.fetchall()

        if not rows:
            conn.close()
            return jsonify({'error': 'No items to export'}), 404

        fieldnames = [description[0] for description in c.description]
        conn.close()

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(dict(row))

        return output.getvalue(), 200, {
            'Content-Disposition': 'attachment; filename="inventory.csv"',
            'Content-Type': 'text/csv'
        }
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    """Get inventory statistics"""
    try:
        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT COUNT(*) as total_items FROM inventory")
        total = c.fetchone()['total_items']

        c.execute("SELECT SUM(amount) as total_value FROM inventory WHERE amount IS NOT NULL")
        value = c.fetchone()['total_value'] or 0

        c.execute("SELECT COUNT(DISTINCT location_installed) as locations FROM inventory WHERE location_installed IS NOT NULL")
        locations = c.fetchone()['locations']

        conn.close()

        return jsonify({
            'total_items': total,
            'total_value': value,
            'locations': locations
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug)
