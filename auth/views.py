from flask import Blueprint, request
from flask.views import MethodView
import json
from .models import *
from .serializers import *
from . import permissions
from utils.general_utils import *
from utils.generic_views import RetrieveUpdateAPIView
from flask_jwt_extended import (
    jwt_required, get_jwt_identity,
    create_access_token
)
from flask_bcrypt import (
    generate_password_hash, check_password_hash)
from db.exceptions import (
    CustomValidationFailedException,
    ObjectCanNotBeDeletedException
)


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
    account = Account.create(title=f"myaccount@{user.username}")
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


class AddRemoveUserFromAccountView(RetrieveUpdateAPIView):
    """ Provides functionality to add or remove users from Accounts
        through secondary UserHoldsAccount edges

        TODO: Also add functionality to REMOVE user from account (DELETE)
    """
    serializer = AccountDetailSchema
    vertex_class = Account

    def get_object(self):
        """ Returns the account matching the account id in the url """
        account = Account.filter(id=account_id)

        return account[0] if account else None

    @jwt_required
    @permissions.account_held_by_user
    def get(self, account=None, user=None, account_id=None):
        """ Overwritten to add the required User-holds-account permission """
        self.get_object = lambda: account
        return super().get()

    @jwt_required
    @permissions.account_held_by_user
    def put(self, account=None, user=None, account_id=None):
        """ Endpoint used for adding a user to the given account with a
            secondary relationship
        """
        data = json.loads(request.data)

        if "user" not in data:
            return jsonify_response({
                "error": "User not provided."
            }, 401)

        # Creating a new edge from the user to the account
        try:
            edge = UserHoldsAccount.create(
                user=data["user"], account=account.id,
                relationType="secondary")
        except CustomValidationFailedException as e:
            return jsonify_response({
                "error": e.message
            }, 400)

        response = AccountDetailSchema().dumps(account).data
        return jsonify_response(json.loads(response), 200)

    @jwt_required
    @permissions.account_held_by_user
    def delete(self, account=None, user=None, account_id=None):
        """ Endpoint used for removing a User-Account edge """
        data = json.loads(request.data)
        target_user = data["user"]

        edge = UserHoldsAccount.filter(outv_id=target_user, inv_id=account.id)

        if not edge:
            return jsonify_response({
                "error": "No edge exists between the targeted user and account"
            }, 404)

        try:
            edge[0].delete()
        except ObjectCanNotBeDeletedException as e:
            return jsonify_response({
                "error": e.message
            }, 400)

        response = AccountDetailSchema().dumps(account).data
        return jsonify_response(json.loads(response), 200)

auth_app.add_url_rule("/account/<account_id>/add_remove_user",
                      view_func=AddRemoveUserFromAccountView.as_view(
                          "add_remove_user_from_account"))
