from flask import Blueprint, request
from flask.views import MethodView
import auth
from .models import *
from .serializers import *
from . import permissions
from flask_jwt_extended import (
    jwt_required, get_jwt_identity
)
from utils import *
import json


core_app = Blueprint("core", __name__)


class TeamsListCreateView(MethodView):
    """ Contains all of the Basic GET/POST methods for Listing (GET) and
        Creating (POST) teams
    """
    @jwt_required
    @permissions.account_held_by_user
    def get(self, account=None, user=None, account_id=None):
        """ A GET endpoint that returns all of the teams connected to this
            account
        """
        teams = auth.AccountOwnsTeam.get_teams(account.id)

        schema = TeamSchema(many=True)
        return jsonify_response(schema.dumps(teams).data, 200)

    @jwt_required
    @permissions.account_held_by_user
    def post(self, account=None, user=None, account_id=None):
        """ A POST endpoint used for the creation of new Teams through an
            account linked to the currently authenticated user
        """
        schema = TeamSchema()
        data = schema.loads(request.data)
        if data.errors:
            return jsonify_response(data.errors, 400)

        team = Team.create(**data.data)
        account_edge = auth.AccountOwnsTeam.create(account=account.id, team=team.id)
        user_edge = auth.UserAssignedToCoreVertex.create(
            user=user.id, team=team.id, role="admin")

        return jsonify_response(schema.dumps(team).data, 201)

core_app.add_url_rule("/account/<account_id>/teams",
                      view_func=TeamsListCreateView.as_view("teams"))


class CoreVertexListCreateView(MethodView):
    """ Contains the GET and POST views required for Listing and Creating
        CoreVertex instances (excluding Teams since teams don't have parents)
    """
    @jwt_required
    @permissions.has_core_vertex_parental_permissions
    def get(self, vertex_type=None,
            parent_id=None):
        """ Returns all projects under the given parent's identifier """
        pass

    @jwt_required
    @permissions.has_core_vertex_parental_permissions
    def post(self, parent_vertex=None, vertex_type=None,
             parent_id=None):
        """ Creates the core vertex instance of the given type as well as
            and edge from the parent to the created vertex
        """
        pass

core_app.add_url_rule("/<parent_id>/<vertex_type>/",
                      view_func=CoreVertexListCreateView
                      .as_view("core_vertices"))


class CoreVertexRolesView(MethodView):
    """ Container for all the core vertices' roles endpoint;
            Returns the role owned by the user (current | input) on GET,
            Adds new role on POST
        This view can be used for retrieving and creating new roles for
        a core vertex of types Team | Project | Topic
    """
    def handle_input_target_user(self, current_user_id):
        """ Handles conditional block for fetching the "input_user" or
            the current user based on the request query parameter
            Returns the (<target_user>, <error>) as a tuple
        """
        input_user = request.args.get("user", None)

        if input_user:
            target_user = auth.User.filter(id=input_user)
            if not target_user:
                return None, jsonify_response(
                    {"error": "Input User does not exist."}, 404)
            target_user = target_user[0]
        else:
            target_user = auth.User.filter(id=current_user_id)[0]

        return target_user, None

    @jwt_required
    @permissions.any_core_vertex_role_required
    def get(self, vertex_id=None, core_vertex=None,
            vertex_type=None, current_user_role=None):
        """ Returns the role owned by the current user/input user (?user)
            arg
        """
        current_user = get_jwt_identity()

        target_user, error = self.handle_input_target_user(current_user)
        if error:
            return error

        assigned_role = auth.UserAssignedToCoreVertex(
            inv_label=vertex_type).get_user_assigned_role(
            core_vertex.id, target_user.id)

        return jsonify_response({"role": getattr(assigned_role, "role", None)})

    @jwt_required
    @permissions.any_core_vertex_role_required
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
            target_user_role = auth.UserAssignedToCoreVertex(
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
        edge = auth.UserAssignedToCoreVertex(inv_label=vertex_type) \
            .create(user=target_user.id,
                    role=requested_role,
                    **{vertex_type: core_vertex.id})

        return jsonify_response({
            "user": target_user.id,
            "team": core_vertex.id,
            "role": edge.role
        }, 200)

core_app.add_url_rule(
    "/<vertex_type>/<vertex_id>/roles",
    view_func=CoreVertexRolesView.as_view("core_vertex_roles"))
