from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, get_jwt_claims
)
import json
from db.models import *
from serializers import *
from flask_bcrypt import Bcrypt
from settings import *
from db import client


app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = SECRET_KEY
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

def jsonify_response(data, status_code=200):
    """ Returns a response object with the given data of mimetype
        application/json with the given status code
    """
    return app.response_class(response=json.dumps(data),
                              status=status_code,
                              mimetype="application/json")


@app.route("/", methods=["GET"])
def index():
    """ Base index page for server configuration testing """
    return jsonify({
        "message": "Success!"
    })


@app.route("/register", methods=["POST"])
def register():
    """ A POST Endpoint used for creation of new Users (and their primary
        accounts, indirectly)
    """
    schema = UserRegistrationSchema()

    data = schema.loads(request.data)
    if data.errors:
        return jsonify(data.errors), 400

    # Confirming that a duplicate user doesn't exist
    duplicates_q = f"g.V().hasLabel('{User.LABEL}')" + \
                   f".or(has('username', '{data.data['username']}')," + \
                   f"has('email', '{data.data['email']}'))"
    duplicates = client.submit(duplicates_q).all().result()
    if duplicates:
        return jsonify_response({"error": "User already exists!"}, 400)

    data.data["password"] = bcrypt.generate_password_hash(
        data.data["password"]).decode("utf-8")

    # Creating the User and it's primary account
    user = User.create(**data.data)
    account = Account.create(title=f"Primary Account for {user.fullName}")
    edge = UserHoldsAccount.create(user=user.id, account=account.id,
                                   relationType="primary")

    response = {
        "user": schema.dumps(user).data,
        "token": create_access_token(identity=user)
    }

    return jsonify_response(response, 201)


@app.route("/login", methods=["POST"])
def login():
    """ Login POST Endpoint that returns the JWT Token for the given
        user credentials
    """
    data = json.loads(request.data)
    username, password = data["username"], data["password"].encode("utf-8")

    user = User.filter(username=username)
    if not user:
        return jsonify_response({"User doesn't exist!"}, 404)
    user = user[0]

    if not bcrypt.check_password_hash(user.password.encode("utf-8"), password):
        return jsonify_response({"status": "Password invalid"}, 403)

    response = {
        "user": {
            "username": user.username,
            "email": user.email,
            "fullName": user.fullName,
            "id": user.id
        },
        "token": create_access_token(identity=user)
    }
    return jsonify_response(response, 200)


@app.route("/create_account", methods=["POST"])
@jwt_required
def create_account():
    """ POST endpoint used for creating new secondary Accounts linked
        to the currently authenticated user
    """
    user_id = get_jwt_identity()
    user = User.filter(id=user_id)[0]
    data = json.loads(request.data)

    if 'title' not in data:
        return jsonify_response({"errors": "`title` field is required."}, 400)

    held_accounts = user.get_held_accounts()
    if held_accounts:
        user_accounts = ",".join(f"'{i}'" for i in held_accounts)
        user_account_names_q = \
            f"g.V().hasLabel('{Account.LABEL}')" + \
            f".has('id', within({user_accounts}))" + \
            f".values('title')"
        user_account_names = client.submit(user_account_names_q).all().result()

        if data["title"] in user_account_names:
            return jsonify_response(
                {"errors": "Users with the title already exist"}, 400)

    account = Account.create(title=data["title"])
    edge = UserHoldsAccount.create(user=user.id, account=account.id,
                                   relationType="secondary")

    response = {
        "title": account.title
    }
    return jsonify_response(response, 201)


@app.route("/account/<account_id>/team", methods=["POST"])
@jwt_required
def create_team(account_id):
    """ A POST endpoint used for the creation of new Teams through an account
        linked to the currently authenticated user

        TODO: Add part that verifies that this account is somehow connected
            to the authenticated user
    """
    user_id = get_jwt_identity()
    user = User.filter(id=user_id)[0]

    account = Account.filter(id=account_id)
    if not account:
        return jsonify_response({"error": "Account does not exist!"}, 404)
    account = account[0]

    # Confirming that the account is a user account
    user_accounts = user.get_held_accounts()
    if not account.id in user_accounts:
        return jsonify_response({"error": "Account is not held by the user."},
                                403)

    schema = TeamSchema()
    data = schema.loads(request.data)
    if data.errors:
        return jsonify_response(data.errors, 400)

    team = Team.create(**data.data)
    edge = AccountOwnsTeam.create(account=account.id, team=team.id)

    return jsonify_response(schema.dumps(team).data, 201)


if __name__ == "__main__":
    app.run(debug=True)
