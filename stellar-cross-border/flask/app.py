# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
import stellar_sdk
from stellar_sdk import (
    Keypair,
    Server,
    TransactionBuilder,
    Network,
    Asset,
    Payment,
    Signer,  # <-- Explicit import for Payment operation
    SetOptions,  # <-- For set_options operations
    CreateAccount  # <-- If you need account creation
)
import requests
import os
from stellar_sdk import Signer  # Add this import

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Use testnet configuration
HORIZON_URL = "https://horizon-testnet.stellar.org"
NETWORK_PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE
FRIENDBOT_URL = "https://friendbot.stellar.org"

server = Server(horizon_url=HORIZON_URL)

# Utility function to fund account using Friendbot
def fund_account(public_key):
    response = requests.get(f"{FRIENDBOT_URL}?addr={public_key}")
    return response.json()

@app.route('/')
def index():
    # Home page allows users to create account, perform payment, or initiate escrow
    return render_template('index.html')

@app.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if request.method == "POST":
        # Generate a new Stellar keypair
        kp = Keypair.random()
        public_key = kp.public_key
        secret = kp.secret

        # Fund account using Friendbot
        try:
            fund_data = fund_account(public_key)
            flash("Account created and funded successfully!", "success")
        except Exception as e:
            flash(f"Error funding account: {str(e)}", "danger")

        return render_template("account_created.html", public_key=public_key, secret=secret)
    return render_template('create_account.html')

@app.route('/send-payment', methods=['GET', 'POST'])
def send_payment():
    if request.method == "POST":
        source_secret = request.form.get('source_secret')
        dest = request.form.get('destination')
        amount = request.form.get('amount')
        try:
            source_kp = Keypair.from_secret(source_secret)
            source_pub = source_kp.public_key
            base_fee = server.fetch_base_fee()

            # Load account
            source_account = server.load_account(account_id=source_pub)

            # Create payment transaction
            tx = TransactionBuilder(
                    source_account=source_account,
                    network_passphrase=NETWORK_PASSPHRASE,
                    base_fee=server.fetch_base_fee()
                ) \
                .append_operation(
                    Payment(
                        destination=dest,
                        asset=Asset.native(),
                        amount=str(amount)
                    )
                ) \
                .set_timeout(30) \
                .build()

            tx.sign(source_kp)
            response = server.submit_transaction(tx)
            flash("Payment successful! Transaction hash: " + response['hash'], "success")
        except Exception as e:
            flash(f"Payment failed: {e}", "danger")
    return render_template('send_payment.html')

@app.route('/initiate-escrow', methods=['GET', 'POST'])
def initiate_escrow():
    """
    For multisig escrow:
    - Creates escrow account with 2/3 multisig requiring 2 signatures (userA, userB, mediator)
    """
    if request.method == "POST":
        user_a_secret = request.form.get('user_a_secret')
        user_b_public = request.form.get('user_b_public')
        mediator_public = request.form.get('mediator_public')
        amount = request.form.get('amount')

        try:
            # Validate and setup accounts
            user_a_kp = Keypair.from_secret(user_a_secret)
            user_a_pub = user_a_kp.public_key

            # Create and fund escrow account
            escrow_kp = Keypair.random()
            escrow_pub = escrow_kp.public_key
            fund_account(escrow_pub)  # Fund with Friendbot
            escrow_account = server.load_account(escrow_pub)

            # Create signer objects
            signer_a = Signer.ed25519_public_key(user_a_pub, weight=1)
            signer_b = Signer.ed25519_public_key(user_b_public, weight=1)
            signer_mediator = Signer.ed25519_public_key(mediator_public, weight=1)

            # Single transaction with correct parameters
            tx = TransactionBuilder(
                source_account=escrow_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=server.fetch_base_fee()
            ).append_operation(
                SetOptions(
                    master_weight=0,
                    low_threshold=2,
                    med_threshold=2,
                    high_threshold=2,
                    signer=signer_a  # Set first signer
                )
            ).append_operation(
                SetOptions(
                    signer=signer_b  # Add second signer
                )
            ).append_operation(
                SetOptions(
                    signer=signer_mediator  # Add third signer
                )
            ).set_timeout(30).build()

            tx.sign(escrow_kp)
            server.submit_transaction(tx)

            # Transfer funds to escrow
            user_a_account = server.load_account(user_a_pub)
            payment_tx = TransactionBuilder(
                source_account=user_a_account,
                network_passphrase=NETWORK_PASSPHRASE,
                base_fee=server.fetch_base_fee()
            ).append_operation(
                Payment(
                    destination=escrow_pub,
                    asset=Asset.native(),
                    amount=str(amount)
                )
            ).set_timeout(30).build()

            payment_tx.sign(user_a_kp)
            server.submit_transaction(payment_tx)

            flash(f'Escrow created! Account: {escrow_pub}', "success")
            return render_template("escrow_created.html",
                                escrow_pub=escrow_pub,
                                escrow_secret=escrow_kp.secret)

        except Exception as e:
            flash(f"Escrow failed: {str(e)}", "danger")

    return render_template('initiate_escrow.html')
if __name__ == '__main__':
    app.run(debug=True)

