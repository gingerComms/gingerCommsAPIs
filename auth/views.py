from flask import Blueprint, request
import json
from .models import *
from .serializers import *
from utils.general_utils import *
from flask_jwt_extended import (
    jwt_required, get_jwt_identity,
    create_access_token
)
from flask_bcrypt import (
    generate_password_hash, check_password_hash)


auth_app = Blueprint("auth", __name__)


@auth_app.route("/register", methods=["POST"])
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

    data.data["password"] = generate_password_hash(
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


@auth_app.route("/login", methods=["POST"])
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

    if not check_password_hash(user.password.encode("utf-8"), password):
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


@auth_app.route("/create_account", methods=["POST"])
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
