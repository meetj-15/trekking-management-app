import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from dotenv import load_dotenv
from models import db, User, Trek, Booking
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'staff':
            abort(403)
        if not current_user.is_approved: 
            flash('Your staff account is pending admin approval.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
        admin = User(username='admin', email='admin@trek.com', password_hash=hashed_pw, role='admin', is_approved=True)
        db.session.add(admin)
        db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            if user.is_blacklisted:
                flash('Your account has been blacklisted.', 'danger')
                return redirect(url_for('login'))
            
            if user.role == 'staff' and not user.is_approved:
                flash('Staff account pending admin approval.', 'warning')
                return redirect(url_for('login'))

            login_user(user)
            return redirect(url_for('dashboard'))
            
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        if role not in ['trekker', 'staff']:
            flash('Invalid role selection.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or Email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        is_approved = True if role == 'trekker' else False 
        
        new_user = User(username=username, email=email, password_hash=hashed_pw, role=role, is_approved=is_approved)
        db.session.add(new_user)
        db.session.commit()
        
        msg = 'Registration successful! ' + ('Please wait for admin approval.' if role == 'staff' else 'You can now log in.')
        flash(msg, 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'staff':
        return redirect(url_for('staff_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    
    total_treks = Trek.query.count()
    total_users_staff = User.query.filter(User.role.in_(['trekker', 'staff'])).count()
    total_bookings = Booking.query.count()
    
    treks = Trek.query.all()
    pending_staff = User.query.filter_by(role='staff', is_approved=False).all()
    
    return render_template(
        'admin_dashboard.html', 
        treks=treks, 
        pending_staff=pending_staff,
        total_treks=total_treks,
        total_users=total_users_staff,
        total_bookings=total_bookings
    )

@app.route('/admin/approve_staff/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_staff(user_id):
    staff = User.query.get_or_404(user_id)
    if staff.role == 'staff':
        staff.is_approved = True
        db.session.commit()
        flash(f'Staff member {staff.username} approved.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/staff/dashboard')
@login_required
@staff_required
def staff_dashboard():
    
    assigned_treks = Trek.query.filter_by(assigned_staff_id=current_user.id).all()
    return render_template('staff_dashboard.html', treks=assigned_treks)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    
    query = request.args.get('q', '')
    location = request.args.get('location', '')
    
    base_query = Trek.query.filter(Trek.status == 'Open')
    
    if query:
        base_query = base_query.filter(Trek.name.ilike(f'%{query}%'))
    if location:
        base_query = base_query.filter(Trek.location.ilike(f'%{location}%'))
        
    available_treks = base_query.all()
    history = Booking.query.filter_by(user_id=current_user.id).all()
    
    return render_template('user_dashboard.html', treks=available_treks, history=history)

@app.route('/book/<int:trek_id>', methods=['POST'])
@login_required
def book_trek(trek_id):
    if current_user.role != 'trekker':
        abort(403)
        
    trek = Trek.query.with_for_update().get_or_404(trek_id) 
    
    if trek.status != 'Open':
        flash('This trek is not open for booking.', 'danger')
    elif trek.available_slots > 0:
        trek.available_slots -= 1
        new_booking = Booking(user_id=current_user.id, trek_id=trek.id, status='Booked')
        db.session.add(new_booking)
        db.session.commit()
        flash('Trek booked successfully!', 'success')
    else:
        flash('Sorry, this trek is fully booked.', 'warning')
        
    return redirect(url_for('user_dashboard'))

@app.route('/api/treks', methods=['GET'])
def api_get_treks():
    treks = Trek.query.all()
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'location': t.location,
        'difficulty': t.difficulty,
        'available_slots': t.available_slots,
        'status': t.status
    } for t in treks])

if __name__ == '__main__':
    app.run(debug=True)