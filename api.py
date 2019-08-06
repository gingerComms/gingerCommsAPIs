from flask import Flask, request, jsonify, make_response
import functools
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity, get_jwt_claims
)
from flask.views import MethodView
import json
from db.models import *
from serializers import *
from flask_bcrypt import Bcrypt
from settings import *
from db import client
from permissions import *


app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = SECRET_KEY
jwt = JWTManager(app)

bcrypt = Bcrypt(app)


def jsonify_response(response, status=200):
    """ Returns the dict response as json with the provided status code """
    return app.response_class(
        response=json.dumps(response),
        status=status, mimetype="application/json")


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


class TeamsListCreateView(MethodView):
    """ Contains all of the Basic GET/POST methods for Listing (GET) and
        Creating (POST) teams
    """
    @jwt_required
    @account_held_by_user
    def get(self, account=None, user=None, account_id=None):
        """ A GET endpoint that returns all of the teams connected to this
            account
        """
        teams = AccountOwnsTeam.get_teams(account.id)

        schema = TeamSchema(many=True)
        return jsonify_response(schema.dumps(teams).data, 200)

    @jwt_required
    @account_held_by_user
    def post(self, account=None, user=None, account_id=None):
        """ A POST endpoint used for the creation of new Teams through an
            account linked to the currently authenticated user
        """
        schema = TeamSchema()
        data = schema.loads(request.data)
        if data.errors:
            return jsonify_response(data.errors, 400)

        team = Team.create(**data.data)
        account_edge = AccountOwnsTeam.create(account=account.id, team=team.id)
        user_edge = UserAssignedToCoreVertex.create(
            user=user.id, team=team.id, role="admin")

        return jsonify_response(schema.dumps(team).data, 201)

app.add_url_rule("/account/<account_id>/teams",
                 view_func=TeamsListCreateView.as_view("teams"))


class CoreVertexListCreateView(MethodView):
    """ Contains the GET and POST views required for Listing and Creating
        CoreVertex instances (excluding Teams since teams don't have parents)
    """
    @has_core_vertex_parental_permissions
    @jwt_required
    def get(self, vertex_type=None,
            parent_id=None):
        """ Returns all projects under the given parent's identifier """
        pass

    @has_core_vertex_parental_permissions
    @jwt_required
    def post(self, parent_vertex=None, vertex_type=None,
             parent_id=None):
        """ Creates the core vertex instance of the given type as well as
            and edge from the parent to the created vertex
        """
        pass

app.add_url_rule("/<parent_id>/<vertex_type>/",
                 CoreVertexListCreateView.as_view("core_vertices"))


class CoreVertexRolesView(MethodView):
    """ Container for all the core vertices' roles endpoint;
            Returns the role owned by the user (current | input) on GET,
            Adds new role on POST
    """
    def handle_input_target_user(self, current_user_id):
        """ Handles conditional block for fetching the "input_user" or
            the current user based on the request query parameter
            Returns the (<target_user>, <error>) as a tuple
        """
        input_user = request.args.get("user", None)

        if input_user:
            target_user = User.filter(id=input_user)
            if not target_user:
                return None, jsonify_response(
                    {"error": "Input User does not exist."}, 404)
            target_user = target_user[0]
        else:
            target_user = User.filter(id=current_user_id)[0]

        return target_user, None

    @jwt_required
    @any_core_vertex_role_required
    def get(self, vertex_id=None, core_vertex=None,
            vertex_type=None, current_user_role=None):
        """ Returns the role owned by the current user/input user (?user)
            arg
        """
        current_user = get_jwt_identity()

        target_user, error = self.handle_input_target_user(current_user)
        if error:
            return error

        assigned_role = UserAssignedToCoreVertex(inv_label=vertex_type) \
            .get_user_assigned_role(core_vertex.id, target_user.id)

        return jsonify_response({"role": getattr(assigned_role, "role", None)})

    @jwt_required
    @any_core_vertex_role_required
    def post(self, vertex_id=None, core_vertex=None,
             vertex_type=None, current_user_role=None):
        """ Adds a new role (or updates the existing role) for the current or
            input user on the given team
        """
        data = json.loads(request.data)
        if "role" not in data:
            return jsonify_response(
                {"error": "Request must include a `role` parameter"}, 400)

        current_user = get_jwt_identity()

        target_user, error = self.handle_input_target_user(current_user)
        if error:
            return error

        if target_user.id == current_user:
            target_user_role = current_user_role
        else:
            target_user_role = UserAssignedToCoreVertex(
                inv_label=vertex_type) \
                .get_user_assigned_role(core_vertex.id, target_user.id)

        # Validation for whether the user has enough permissions to even
        # make this role update
        requested_role = data["role"]
        lacking_role_response = jsonify_response(
            {"error": "User lacks the required role for the role requested."},
            403)
        if current_user_role.role == "member":
            # Since members can't change ANY roles
            return lacking_role_response
        elif current_user_role.role == "lead" and (
                requested_role == "admin" or requested_role == "lead"):
            # Since leads can only control member roles
            return lacking_role_response
        elif current_user_role.role == "admin":
            # Since admins can do it all
            pass

        # Removing all existing edges for the target user against this vertex
        if target_user_role is not None:
            target_user_role.delete()

        # Creating a new assignment for the teamuser pair with the given role
        edge = UserAssignedToCoreVertex(inv_label=vertex_type) \
            .create(user=target_user.id,
                    role=requested_role,
                    **{vertex_type: core_vertex.id})

        return jsonify_response({
            "user": target_user.id,
            "team": core_vertex.id,
            "role": edge.role
        }, 200)

app.add_url_rule("/<vertex_type>/<vertex_id>/roles",
                 view_func=CoreVertexRolesView.as_view("core_vertex_roles"))


if __name__ == "__main__":
    app.run(debug=True)
