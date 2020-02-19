from flask import Blueprint, request
from flask.views import MethodView
import json
from .models import *
from .serializers import *
from . import permissions
from utils.general_utils import *
from utils.generic_views import RetrieveUpdateAPIView, UpdateAPIView
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
from utils.s3_engine import S3Engine


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

    # Creating the User and it's primary account + account admin edge
    user = User.create(**data.data)
    account = Account.create(title=f"myaccount@{user.username}")
    holds_edge = UserHoldsAccount.create(user=user.id, account=account.id,
                                         relationType="primary")
    admin_edge = UserIsAccountAdmin.create(user=user.id, account=account.id)

    response = {
        "user": json.loads(schema.dumps(user).data),
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
        return jsonify_response({"status": "User doesn't exist!"}, 404)
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

    held_accounts = user.get_held_accounts(user.id)
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


class ListCreateAccountsView(MethodView):
    """ Implements a LIST GET API for accounts """

    @jwt_required
    def get(self):
        """ Returns a serialized list of accounts that the authenticated
            user has access to
        """
        held_accounts = User.get_held_accounts(
            get_jwt_identity(), initialize_models=True)

        schema = AccountsListSchema(many=True)
        response = schema.dumps(held_accounts)

        return jsonify_response(json.loads(response.data), 200)

    @jwt_required
    def post(self):
        """ POST endpoint used for creating new secondary Accounts linked
            to the currently authenticated user
        """
        data = json.loads(request.data)
        user_id = get_jwt_identity()

        if 'title' not in data:
            return jsonify_response({"errors": "`title` field is required."}, 400)

        held_accounts = User.get_held_accounts(user_id)
        if held_accounts:
            user_accounts = ",".join(f"'{i}'" for i in held_accounts)
            user_account_names_q = \
                f"g.V().hasLabel('{Account.LABEL}')" + \
                f".has('id', within({user_accounts}))" + \
                f".values('title')"
            user_account_names = client.submit(user_account_names_q).all().result()

            if data["title"] in user_account_names:
                return jsonify_response(
                    {"errors": "Account with the given title already exists"},
                    400)

        account = Account.create(title=data["title"])
        held_edge = UserHoldsAccount.create(user=user_id, account=account.id,
                                            relationType="secondary")
        admin_edge = UserIsAccountAdmin.create(user=user_id,
                                               account=account.id)

        response = {
            "title": account.title,
            'id': account.id,
            "admins": json.loads(UserListSchema(many=True)
                                 .dumps(User.filter(id=user_id)).data)
        }
        return jsonify_response(response, 201)
auth_app.add_url_rule("/accounts/",
                      view_func=ListCreateAccountsView.as_view(
                          "list_create_accounts"))


class UpdateAccountView(UpdateAPIView):
    """ Provides functionality for full/partial updates of an
        account's details through PUT/PATCH methods
    """
    serializer_class = AccountDetailSchema
    vertex_class = Account

    def get_vertex_id(self):
        return request.view_args["account_id"]

    # TODO: Add is account admin permission
    @jwt_required
    @permissions.account_held_by_user
    def put(self, account=None, user=None, account_id=None):
        """ Overridden to add the permission decorator """
        return super().put()

    # TODO: Add is account admin permission
    @jwt_required
    @permissions.account_held_by_user
    def patch(self, account=None, user=None, account_id=None):
        """ Overridden to add the permission decorator """
        return super().patch()

auth_app.add_url_rule("/account/<account_id>",
                      view_func=UpdateAccountView.as_view(
                          "update_account"))


class UploadAccountAvatarView(MethodView):
    """ Endpoint providing functionality for uploading (and overwriting)
        the given account's avatar
    """
    # TODO: Add is account admin permission
    @jwt_required
    @permissions.account_held_by_user
    def put(self, account=None, user=None, account_id=None):
        """ Overridden to add the permission decorator """
        file = request.files.get('file')
        filename = f"{account_id}/avatar.img"

        engine = S3Engine()
        url = engine.put_object(filename, file.read())
        Account.update(vertex_id=account_id,
                       validated_data={"avatarLink": url})

        return jsonify_response({
            "id": account.id,
            "title": account.title,
            "avatarLink": url
        })


auth_app.add_url_rule("/account/<account_id>/avatar",
                      view_func=UploadAccountAvatarView.as_view(
                          "upload_account_avatar"))


class RetrieveCreateRemoveAccountAdminsView(RetrieveUpdateAPIView):
    """ Provides functionality to add, remove and list Users who hold
        an admin position for the given account through the
        UserIsAccountAdmin edge
    """
    serializer_class = AccountDetailSchema
    vertex_class = Account

    def get_object(self):
        """ Returns the account matching the account id in the url with
            it's admins
        """
        account = Account.get_account_with_admins(account.id)

        return account[0] if account else None

    @jwt_required
    @permissions.account_held_by_user
    def get(self, account=None, user=None, account_id=None):
        """ Overwritten to add the required User-holds-account permission
            - Returns the account detail for the given account
        """
        self.get_object = lambda: account
        return super().get()

    # TODO: Add is account admin permission
    @jwt_required
    @permissions.account_held_by_user
    def post(self, account=None, user=None, account_id=None):
        """ Endpoint used for adding a user to the given account
            as an admin
        """
        data = json.loads(request.data)

        if "user" not in data:
            return jsonify_response({
                "error": "User not provided."
            }, 401)

        # Checking if this edge already exists
        admin_edge = UserIsAccountAdmin.filter(
            outv_id=data["user"], inv_id=account.id)
        if admin_edge:
            return jsonify_response({
                "error": "User is already an admin for this account."
            }, 401)

        # Creating a new edge from the user to the account
        admin_edge = UserIsAccountAdmin.create(
            user=data["user"], account=account.id)

        # Creating a holds edge if one doesn't already exist
        query = f"g.V().has('{User.LABEL}', 'id', '{data['user']}')" + \
            f".outE('{UserHoldsAccount.LABEL}').as('e')" + \
            f".inV().has('id', '{account.id}')" + \
            f".select('e').fold().coalesce(" + \
            f"unfold(), g.V().has('{User.LABEL}', 'id', '{data['user']}')" + \
            f".addE('{UserHoldsAccount.LABEL}')" + \
            f".to(g.V().has('{Account.LABEL}'," + \
            f"'id', '{account.id}')).property('relationType', 'secondary'))"
        holds_edge = client.submit(query).all().result()

        response = UserListSchema().dumps(
            User.filter(id=data["user"])[0]).data
        return jsonify_response(json.loads(response), 201)

    # TODO: Add is account admin permission
    @jwt_required
    @permissions.account_held_by_user
    def delete(self, account=None, user=None, account_id=None):
        """ Endpoint used for removing a User-Admin edge """
        print(request.data)
        data = json.loads(request.data)
        target_user = data["user"]

        admin_edge = UserIsAccountAdmin.filter(outv_id=target_user,
                                         inv_id=account.id)

        if not admin_edge:
            return jsonify_response({
                "error": "No edge exists between the targeted user and account"
            }, 404)

        try:
            admin_edge[0].delete()
        except ObjectCanNotBeDeletedException as e:
            return jsonify_response({
                "error": e.message
            }, 400)

        response = AccountDetailSchema().dumps(account).data
        return jsonify_response(json.loads(response), 200)

auth_app.add_url_rule("/account/<account_id>/admins",
                      view_func=RetrieveCreateRemoveAccountAdminsView.as_view(
                          "add_remove_user_from_account"))


class UserListView(MethodView):
    """ Endpoint that provides a LIST GET for users;
        mainly used for search purposes
    """
    @jwt_required
    def get(self):
        """ Returns the account matching the account id in the url with
            it's admins
        """
        queries = {"wildcard_properties": []}

        fullname_query = request.args.get("fullName", None)
        email_query = request.args.get("email", None)

        if fullname_query:
            queries["fullName"] = f"TextP.startingWith('{fullname_query}')"
            queries["wildcard_properties"].append("fullName")
        if email_query:
            queries["fullName"] = f"TextP.startingWith('{email_query}')"
            queries["wildcard_properties"].append("email")

        users = User.filter(limit=10, **queries)
        response = UserListSchema(many=True).dumps(users).data

        return jsonify_response(json.loads(response), 200)

auth_app.add_url_rule("/users",
                      view_func=UserListView.as_view(
                          "users_search"))
