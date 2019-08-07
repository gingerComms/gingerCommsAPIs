from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from settings import *


app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = SECRET_KEY

# Registering the sub-modules
from auth.views import auth_app
from core.views import core_app

app.register_blueprint(auth_app, url_prefix="/auth")
app.register_blueprint(core_app)

jwt = JWTManager(app)

bcrypt = Bcrypt(app)


@jwt.user_claims_loader
def add_user_details_to_jwt_token(user):
    """ Returns the data that will be added to the jwt payload """
    return {
        "username": user.username,
        "email": user.email,
        "id": user.id
    }


@jwt.user_identity_loader
def user_identity_lookup(user):
    """ Returns the identity field to be used in the jwt token """
    return user.id


@app.route("/", methods=["GET"])
def index():
    """ Base index page for server configuration testing """
    return jsonify({
        "message": "Success!"
    })


if __name__ == "__main__":
    app.run(debug=True)
