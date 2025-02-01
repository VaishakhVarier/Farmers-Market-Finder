from flask import Flask, request, jsonify, flash, render_template, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Secret key for session management
app.secret_key = 'your_secret_key'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farmers_market.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)  # Initialize SocketIO for real-time communication

# ======================== Database Models ========================

# Farmer model
class Farmer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

# Product model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('farmer.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)

    farmer = db.relationship('Farmer', backref=db.backref('products', lazy=True))

# Pre-order model
class PreOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('farmer.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(50), nullable=False)

    product = db.relationship('Product', backref=db.backref('preorders', lazy=True))
    farmer = db.relationship('Farmer', backref=db.backref('preorders', lazy=True))

# Market model (for location-based searches)
class Market(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    produce_available = db.Column(db.String(500), nullable=False)  # Comma-separated produce list

# ======================== Database Initialization ========================

# Predefined farmer users
farmers = {
    'siddhanta': 'farmer123',
    'Smith': 'farmer456',
}

with app.app_context():
    db.create_all()

    # Create farmers if they don't exist in the database
    for username, password in farmers.items():
        if not Farmer.query.filter_by(username=username).first():
            new_farmer = Farmer(username=username, password_hash=generate_password_hash(password))
            db.session.add(new_farmer)
    db.session.commit()

    # Sample markets
    if not Market.query.first():
        sample_markets = [
            Market(name="Green Valley Market", location="Mumbai", produce_available="Tomato, Onion, Potato"),
            Market(name="Fresh Farm Hub", location="Pune", produce_available="Carrot, Cabbage, Spinach"),
        ]
        db.session.add_all(sample_markets)
        db.session.commit()

# ======================== Routes ========================

# Home route (Admin Dashboard)
@app.route('/')
def home():
    if 'username' in session:
        return render_template('admin.html', username=session['username'])
    return redirect(url_for('login'))

# Farmer Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if Farmer.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        new_farmer = Farmer(username=username, password_hash=password_hash)
        db.session.add(new_farmer)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

# Farmer Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        farmer = Farmer.query.filter_by(username=username).first()

        if farmer and check_password_hash(farmer.password_hash, password):
            session['username'] = username
            return redirect(url_for('home'))
        else:
            return "Invalid credentials", 401
    return render_template('login.html')

# Farmer Logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# ======================== Product Management ========================

# Add Product
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    farmer = Farmer.query.filter_by(username=session['username']).first()
    data = request.json

    product = Product(
        farmer_id=farmer.id,
        name=data['name'],
        price=data['price'],
        stock=data['stock']
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({'message': 'Product added successfully!'}), 200

# Delete Product
@app.route('/delete_product', methods=['POST'])
def delete_product():
    if 'username' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    data = request.json
    product_id = data['product_id']
    farmer = Farmer.query.filter_by(username=session['username']).first()
    product = Product.query.filter_by(id=product_id, farmer_id=farmer.id).first()

    if product:
        db.session.delete(product)
        db.session.commit()
        return jsonify({'message': 'Product deleted successfully!'}), 200
    else:
        return jsonify({'message': 'Product not found'}), 404

# Get Products
@app.route('/get_products', methods=['GET'])
def get_products():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    farmer = Farmer.query.filter_by(username=session['username']).first()
    products = Product.query.filter_by(farmer_id=farmer.id).all()

    return jsonify([{
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'stock': product.stock
    } for product in products])

# Update Product
@app.route('/update_product', methods=['POST'])
def update_product():
    if 'username' not in session:
        return jsonify({'message': 'Unauthorized'}), 401

    farmer = Farmer.query.filter_by(username=session['username']).first()
    data = request.json
    product_id = data.get('product_id')
    new_stock = data.get('new_stock')
    new_price = data.get('new_price')

    product = Product.query.filter_by(id=product_id, farmer_id=farmer.id).first()
    if product:
        product.stock = new_stock
        product.price = new_price
        db.session.commit()
        return jsonify({'message': 'Product updated successfully!'})
    return jsonify({'message': 'Product not found'}), 404

# ======================== Customer Features ========================

# Customer Page
@app.route('/customer_page')
def customer_page():
    return render_template('customer.html')

# Place Pre-order
@app.route('/pre_order', methods=['POST'])
def pre_order():
    data = request.json
    product_id = data['product_id']
    customer_name = data['customer_name']
    quantity = data['quantity']
    contact = data['contact']

    pre_order_entry = PreOrder(
        farmer_id=Product.query.get(product_id).farmer_id,
        product_id=product_id,
        customer_name=customer_name,
        quantity=quantity,
        contact=contact
    )
    db.session.add(pre_order_entry)
    db.session.commit()

    # Real-time notification to admins
    socketio.emit('new_order', {
        'customer_name': customer_name,
        'product_name': Product.query.get(product_id).name,
        'quantity': quantity,
        'contact': contact
    }, broadcast=True)

    return jsonify({'message': 'Pre-order placed successfully!'})

# Get Pre-orders (for farmers)
@app.route('/get_preorders', methods=['GET'])
def get_preorders():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    farmer = Farmer.query.filter_by(username=session['username']).first()
    pre_orders = PreOrder.query.filter_by(farmer_id=farmer.id).all()

    return jsonify([{
        'customer_name': pre_order.customer_name,
        'product_name': pre_order.product.name,
        'quantity': pre_order.quantity,
        'contact': pre_order.contact
    } for pre_order in pre_orders])

# ======================== Market Search ========================

@app.route('/markets')
def market_list():
    markets = Market.query.all()
    return render_template('customer.html', markets=markets)

@app.route('/search_market', methods=['GET'])
def search_market():
    query = request.args.get('query', '').lower()
    search_type = request.args.get('type', 'location')

    if search_type == 'produce':
        products = Product.query.filter(Product.name.ilike(f"%{query}%")).all()
        results = [{
            'farmer_name': product.farmer.username,
            'product_name': product.name,
            'price': product.price,
            'stock': product.stock
        } for product in products]
        return jsonify(results)
    else:
        markets = Market.query.filter(Market.location.ilike(f"%{query}%")).all()
        return jsonify([{
            'id': market.id,
            'name': market.name,
            'location': market.location,
            'produce_available': market.produce_available
        } for market in markets])

# ======================== Real-Time Notifications ========================

@socketio.on('new_order')
def handle_new_order(data):
    emit('update_preorders', data, broadcast=True)

# ======================== Run the App ========================
if __name__ == '__main__':
    socketio.run(app, debug=True)
