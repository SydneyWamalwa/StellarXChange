# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import stellar_sdk
from stellar_sdk import (
    Keypair,
    Server,
    TransactionBuilder,
    Network,
    Asset,
    Payment,
    Signer,
    SetOptions
)
import requests
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from decimal import Decimal
app = Flask(__name__)
app.secret_key = os.urandom(24)
from flask_migrate import Migrate
from functools import lru_cache
import time

# Add caching decorator (updates every 5 minutes)
@lru_cache(maxsize=32)
def get_xlm_price(currency='USD'):
    """Get current XLM price with caching"""
    try:
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies={currency}')
        return Decimal(response.json()['stellar'][currency.lower()])
    except Exception as e:
        return Decimal('0.10')

# Configure SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stellarpay.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Stellar configuration for testnet
HORIZON_URL = "https://horizon-testnet.stellar.org"
NETWORK_PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE
FRIENDBOT_URL = "https://friendbot.stellar.org"
server = Server(horizon_url=HORIZON_URL)

##########################################################
# Database Models
##########################################################

# Update User model to track currency preferences
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    stellar_public_key = db.Column(db.String(56), nullable=False)
    stellar_secret_key = db.Column(db.String(56), nullable=False) #Encrypt in production
    country = db.Column(db.String(50), default='KE')  # KE for Kenya, IN for India
    local_currency = db.Column(db.String(3), default='KES')  # KES, INR, etc

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Escrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)
    receiver_public_key = db.Column(db.String(56), nullable=False)
    mediator_public_key = db.Column(db.String(56), nullable=True)
    escrow_public_key = db.Column(db.String(56), nullable=False)
    escrow_secret_key = db.Column(db.String(56), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, released, locked
    deadline = db.Column(db.DateTime, nullable=False)
    approvals = db.Column(db.Integer, default=0)  # New field for tracking approvals
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_expired(self):
        return datetime.utcnow() > self.deadline

##########################################################
# Utility Functions
##########################################################

def fund_account(public_key):
    response = requests.get(f"{FRIENDBOT_URL}?addr={public_key}")
    return response.json()

def get_base_fee():
    return server.fetch_base_fee()

def get_xlm_price(currency='USD'):
    """Get current XLM price from CoinGecko API"""
    try:
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies={currency}')
        return Decimal(response.json()['stellar'][currency.lower()])
    except Exception as e:
        return Decimal('0.10')  # Fallback value
def convert_to_local(xlm_amount, currency):
    """Convert XLM amount to local currency"""
    rate = get_xlm_price(currency)
    return Decimal(xlm_amount) * rate

def convert_to_xlm(amount, currency):
    rate = get_xlm_price(currency)
    return Decimal(amount) / rate

##########################################################
# Utility Functions (Updated)
##########################################################

def get_xlm_price(currency='USD'):
    """Get current XLM price from CoinGecko API"""
    try:
        response = requests.get(f'https://api.coingecko.com/api/v3/simple/price?ids=stellar&vs_currencies={currency}')
        return Decimal(response.json()['stellar'][currency.lower()])
    except Exception as e:
        return Decimal('0.10')  # Fallback value

def convert_to_xlm(amount, currency):
    """Convert local currency to XLM"""
    rate = get_xlm_price(currency)
    return Decimal(amount) / rate

def convert_to_local(xlm_amount, currency):  # <-- ADD THIS
    """Convert XLM to local currency"""
    rate = get_xlm_price(currency)
    return Decimal(xlm_amount) * rate

def get_stellar_balance(public_key):
    """Get XLM balance from Stellar network"""
    try:
        account = server.accounts().account_id(public_key).call()
        for balance in account['balances']:
            if balance['asset_type'] == 'native':
                return Decimal(balance['balance'])
        return Decimal('0')
    except:
        return Decimal('0')

##########################################################
# Authentication Endpoints
##########################################################

@app.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        # Check if user already exists
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("User already exists", "danger")
            return redirect(url_for('create_account'))

        kp = Keypair.random()
        public_key = kp.public_key
        secret = kp.secret

        try:
            fund_account(public_key)
            flash("Account created and funded successfully!", "success")
        except Exception as e:
            flash(f"Error funding account: {str(e)}", "danger")
            return redirect(url_for('create_account'))

        user = User(
            username=username,
            email=email,
            stellar_public_key=public_key,
            stellar_secret_key=secret
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        # Auto-login the user after signup
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash("Login successful", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('login'))

##########################################################
# Profile Page (Accessible via Nav Bar)
##########################################################

@app.route('/profile', methods=['GET'])
def profile():
    user_id = session.get('user_id')
    if not user_id:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('login'))
    # By default, hide secret key
    show_keys = request.args.get('show_keys', 'false').lower() == 'true'
    user_data = {
        "username": user.username,
        "email": user.email,
        "stellar_public_key": user.stellar_public_key,
        "stellar_secret_key": user.stellar_secret_key if show_keys else "**** (hidden)"
    }
    return render_template("profile.html", user=user_data)

##########################################################
# Payment Endpoint (As Before)
##########################################################

@app.route('/send-payment', methods=['GET', 'POST'])
def send_payment():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == "POST":
        dest_public = request.form.get('destination')
        amount = Decimal(request.form.get('amount'))

        # Get recipient's currency preference
        recipient = User.query.filter_by(stellar_public_key=dest_public).first()
        recipient_currency = recipient.local_currency if recipient else 'XLM'

        # Convert amount to XLM
        if request.form.get('currency') != 'XLM':
            amount = convert_to_xlm(amount, request.form.get('currency'))

        # Show conversion preview
        if 'preview' in request.form:
            xlm_rate = get_xlm_price(recipient_currency)
            converted_amount = amount * xlm_rate
            return render_template('send_payment.html',
                preview=True,
                amount=amount,
                dest=dest_public,
                converted_amount=converted_amount,
                currency=recipient_currency
            )

        # Actual payment logic
        try:
            source_kp = Keypair.from_secret(user.stellar_secret_key)
            source_account = server.load_account(user.stellar_public_key)

            tx = TransactionBuilder(
                source_account=source_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=get_base_fee()
            ).append_payment_op(
                destination=dest_public,
                asset=Asset.native(),
                amount=str(amount)
            ).set_timeout(30).build()

            tx.sign(source_kp)
            response = server.submit_transaction(tx)

            flash(f"Sent {amount:.2f} XLM ({convert_to_local(amount, recipient_currency):.2f} {recipient_currency})", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Payment failed: {e}", "danger")

    return render_template('send_payment.html', balance=get_stellar_balance(user.stellar_public_key))

##########################################################
# Escrow Endpoint (Simplified Version)
##########################################################

@app.route('/initiate-escrow', methods=['GET', 'POST'])
def initiate_escrow():
    if not session.get('user_id'):
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    if request.method == "POST":
        user_a_secret = request.form.get('user_a_secret')
        user_b_public = request.form.get('user_b_public')
        mediator_public = request.form.get('mediator_public')
        amount = request.form.get('amount')
        try:
            user_a_kp = Keypair.from_secret(user_a_secret)
            user_a_pub = user_a_kp.public_key

            # Create and fund escrow account
            escrow_kp = Keypair.random()
            escrow_pub = escrow_kp.public_key
            escrow_secret = escrow_kp.secret
            fund_account(escrow_pub)
            escrow_account = server.load_account(escrow_pub)

            signer_a = Signer.ed25519_public_key(user_a_pub, weight=1)
            signer_b = Signer.ed25519_public_key(user_b_public, weight=1)
            signer_mediator = Signer.ed25519_public_key(mediator_public, weight=1)
            base_fee = get_base_fee()

            tx = TransactionBuilder(
                source_account=escrow_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=base_fee
            ).append_operation(
                SetOptions(
                    master_weight=0,
                    low_threshold=2,
                    med_threshold=2,
                    high_threshold=2,
                    signer=signer_a
                )
            ).append_operation(
                SetOptions(
                    signer=signer_b
                )
            ).append_operation(
                SetOptions(
                    signer=signer_mediator
                )
            ).set_timeout(30).build()

            tx.sign(escrow_kp)
            server.submit_transaction(tx)

            user_a_account = server.load_account(user_a_pub)
            payment_tx = TransactionBuilder(
                source_account=user_a_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=get_base_fee()
            ).append_operation(
                Payment(
                    destination=escrow_pub,
                    asset=Asset.native(),
                    amount=str(amount)
                )
            ).set_timeout(30).build()

            payment_tx.sign(user_a_kp)
            server.submit_transaction(payment_tx)

            deadline = (datetime.utcnow() + timedelta(minutes=60)).isoformat()
            new_escrow = Escrow(
                sender_id=session.get('user_id'),
                receiver_public_key=user_b_public,
                mediator_public_key=mediator_public,
                escrow_public_key=escrow_pub,
                escrow_secret_key=escrow_secret,
                amount=amount,
                status='pending',
                deadline=datetime.fromisoformat(deadline),
                approvals=0
            )
            db.session.add(new_escrow)
            db.session.commit()
            flash(f'Escrow created! Account: {escrow_pub}. Deadline for approvals: {deadline}', "success")
            return render_template("escrow_created.html", escrow_pub=escrow_pub, escrow_secret=escrow_secret, deadline=deadline)
        except Exception as e:
            flash(f"Escrow failed: {str(e)}", "danger")
    return render_template('initiate_escrow.html')

@app.route('/approve-escrow/<int:escrow_id>', methods=['GET', 'POST'])
def approve_escrow(escrow_id):
    # Lookup the escrow record from the database
    escrow = Escrow.query.get(escrow_id)
    if not escrow:
        flash("Escrow not found", "danger")
        return redirect(url_for('index'))

    # If escrow is pending but deadline is reached, update status
    if escrow.is_expired() and escrow.status == 'pending':
        escrow.status = 'locked'
        db.session.commit()
        flash("Escrow deadline reached. Escrow is now locked.", "danger")
        return redirect(url_for('index'))

    if request.method == "POST":
        # Register an approval (you might later associate which party approved)
        escrow.approvals += 1

        # For demonstration, require 2 approvals to mark as approved
        if escrow.approvals >= 2:
            escrow.status = 'approved'
            flash("Escrow approved! Funds can now be disbursed.", "success")
        else:
            flash("Your approval has been recorded. Waiting for additional approvals.", "info")
        db.session.commit()
        return redirect(url_for('approve_escrow', escrow_id=escrow_id))

    # Calculate remaining time in seconds for a real-time countdown
    remaining_seconds = int((escrow.deadline - datetime.utcnow()).total_seconds())
    if remaining_seconds < 0:
        remaining_seconds = 0

    return render_template('approve_escrow.html', escrow=escrow, remaining_seconds=remaining_seconds)


@app.route('/escrow-approvals', methods=['GET'])
def escrow_approvals():
    # Ensure the user is logged in before accessing escrow approvals
    if not session.get('user_id'):
        flash("Please log in to view escrow approvals", "warning")
        return redirect(url_for('login'))

    # Retrieve current user from the database
    user = User.query.get(session.get('user_id'))
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('login'))

    # Query escrow records that are pending and involve the current user in some capacity.
    pending_escrows = Escrow.query.filter(
        Escrow.status == 'pending',
        or_(
            Escrow.sender_id == user.id,
            Escrow.receiver_public_key == user.stellar_public_key,
            Escrow.mediator_public_key == user.stellar_public_key
        )
    ).all()

    return render_template('escrow_approvals.html', escrows=pending_escrows)



##########################################################
# DB Initialization and Home Route
##########################################################

@app.before_request
def create_tables():
    with app.app_context():
        db.create_all()


@app.route('/')
def index():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        balance = get_stellar_balance(user.stellar_public_key)

        user_keys = {
            'public_key': user.stellar_public_key,
            'secret_key': user.stellar_secret_key,
            'balance': balance,
            'local_currency': user.local_currency,
            'xlm_rate': get_xlm_price(user.local_currency)
        }
        return render_template('index.html', user_keys=user_keys)
    else:
        return redirect(url_for('login'))

# Add new routes for fiat deposits
@app.route('/deposit/mpesa', methods=['GET', 'POST'])
def mpesa_deposit():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        amount = Decimal(request.form.get('amount'))

        # Convert KES to XLM
        xlm_amount = convert_to_xlm(amount, 'KES')

        # In real implementation: Call M-Pesa API here
        # For simulation, we'll directly fund the account
        try:
            source_kp = Keypair.from_secret(user.stellar_secret_key)
            server.load_account(user.stellar_public_key)

            # Simulate receiving XLM (in real system, this would come from your XLM reserve)
            flash(f"Simulated M-Pesa deposit: {amount} KES converted to {xlm_amount:.2f} XLM", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Deposit failed: {str(e)}", "danger")

    return render_template('mpesa_deposit.html', rate=get_xlm_price('KES'))

@app.route('/deposit/airtel', methods=['GET', 'POST'])
def airtel_deposit():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        amount = Decimal(request.form.get('amount'))

        # Convert INR to XLM
        xlm_amount = convert_to_xlm(amount, 'INR')

        # Simulate Airtel payment
        try:
            source_kp = Keypair.from_secret(user.stellar_secret_key)
            server.load_account(user.stellar_public_key)

            flash(f"Simulated Airtel deposit: {amount} INR converted to {xlm_amount:.2f} XLM", "success")
            return redirect(url_for('index'))
        except Exception as e:
            flash(f"Deposit failed: {str(e)}", "danger")

    return render_template('airtel_deposit.html', rate=get_xlm_price('INR'))

if __name__ == '__main__':
    app.run(debug=True)
