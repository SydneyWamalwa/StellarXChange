from stellar_sdk import Keypair, Server
from models import db, User
from werkzeug.security import check_password_hash
import os

def create_user_account(username, email, password):
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return {"error": "User already exists"}, 400

    keypair = Keypair.random()
    public_key = keypair.public_key
    secret_key = keypair.secret

    # Activate testnet account via Friendbot
    server = Server("https://horizon-testnet.stellar.org")
    friendbot_url = f"https://friendbot.stellar.org?addr={public_key}"
    os.system(f"curl -s '{friendbot_url}' > /dev/null")

    user = User(
        username=username,
        email=email,
        stellar_public_key=public_key,
        stellar_secret_key=secret_key
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return {
        "message": "User created successfully",
        "public_key": public_key
    }, 201

def login_user(email, password):
    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        # In a real app, generate a token or set session data
        return {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "stellar_public_key": user.stellar_public_key
            }
        }, 200
    else:
        return {"error": "Invalid credentials"}, 401
