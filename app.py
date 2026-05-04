from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, urllib.parse
from collections import Counter
from functools import wraps

app = Flask(__name__)
app.secret_key = 'anyona_secret_key_123' 
app.config['UPLOAD_FOLDER'] = 'static/uploads'

ADMIN_PASSWORD = "Anyona" 

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM clothes").fetchall()
    conn.close()
    return render_template('index.html', items=items, cart_count=len(session.get('cart', [])))

@app.route('/product/<int:item_id>')
def product_detail(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM clothes WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    return render_template('product.html', item=item, cart_count=len(session.get('cart', [])))

@app.route('/add_to_cart/<int:item_id>')
def add_to_cart(item_id):
    if 'cart' not in session:
        session['cart'] = []
    cart_list = session['cart']
    cart_list.append(item_id)
    session['cart'] = cart_list
    return redirect(request.referrer or url_for('index'))

@app.route('/remove_from_cart/<int:item_id>')
def remove_from_cart(item_id):
    if 'cart' in session:
        cart_list = session['cart']
        if item_id in cart_list:
            cart_list.remove(item_id) 
            session['cart'] = cart_list
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    if 'cart' not in session or not session['cart']: 
        return render_template('cart.html', display_items=[], total=0)
    
    counts = Counter(session['cart'])
    conn = get_db_connection()
    placeholders = ', '.join(['?'] * len(counts.keys()))
    rows = conn.execute(f"SELECT * FROM clothes WHERE id IN ({placeholders})", list(counts.keys())).fetchall()
    conn.close()
    
    display_items = []
    total = 0
    for r in rows:
        qty = counts[r['id']]
        subtotal = r['price'] * qty
        total += subtotal
        display_items.append({'id': r['id'], 'name': r['name'], 'price': r['price'], 'qty': qty, 'subtotal': subtotal})
        
    return render_template('cart.html', display_items=display_items, total=total)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        input_password = request.form.get('password', '').strip()
        if input_password == ADMIN_PASSWORD:
            session.permanent = True
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return "<h1>Access Denied</h1>", 403
    return render_template('login.html')

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        file = request.files['image']
        if file:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
            conn.execute("INSERT INTO clothes (name, price, img) VALUES (?, ?, ?)", (name, price, file.filename))
            conn.commit()
        return redirect(url_for('admin'))
    
    items = conn.execute("SELECT * FROM clothes").fetchall()
    conn.close()
    return render_template('admin.html', items=items)

@app.route('/admin/delete/<int:item_id>')
@login_required
def delete_item(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM clothes WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/complete_order', methods=['POST'])
def complete_order():
    name = request.form.get('customer_name')
    phone = request.form.get('customer_phone')
    lat = request.form.get('lat')
    lon = request.form.get('lon')
    
    counts = Counter(session.get('cart', []))
    conn = get_db_connection()
    placeholders = ', '.join(['?'] * len(counts.keys()))
    rows = conn.execute(f"SELECT id, name, price FROM clothes WHERE id IN ({placeholders})", list(counts.keys())).fetchall()
    conn.close()

    whatsapp_number = "+254702872541" 
    message = f"🛍️ *New Order Detail*\n👤 *Name:* {name}\n📞 *Phone:* {phone}\n\n🛒 *Items:*\n"
    
    total = 0
    for row in rows:
        qty = counts[row['id']]
        total += row['price'] * qty
        message += f"• {row['name']} (x{qty})\n"
    
    message += f"\n💰 *Total: ${total}*"
    if lat and lon:
        message += f"\n📍 *Map:* https://www.google.com/maps?q={lat},{lon}"

    session.pop('cart', None)
    return redirect(f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(message)}")

if __name__ == '__main__':
    with get_db_connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS clothes (id INTEGER PRIMARY KEY, name TEXT, price REAL, img TEXT)')
    app.run(host='0.0.0.0', port=5000, debug=True)
