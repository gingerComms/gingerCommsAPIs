from flask import Blueprint, request
from flask.views import MethodView
import auth
from .models import *
from .serializers import *
from . import permissions
from auth import permissions as auth_permissions
from utils.metaclasses import *
from utils.generic_views import RetrieveUpdateAPIView
from utils.mixins import DeleteVertexMixin
from flask_jwt_extended import (
    jwt_required, get_jwt_identity
)
from utils.general_utils import *
import json
from flask_caching import Cache
from db.engine import client


core_app = Blueprint("core", __name__)


class ListCreateTeamsView(MethodView):
    """ Contains all of the Basic GET/POST methods for Listing (GET) and
        Creating (POST) teams
    """
    @jwt_required
    @auth_permissions.account_held_by_user
    def get(self, account=None, user=None, account_id=None):
        """ A GET endpoint that returns all of the teams connected to this
            account
            NOTE [TODO]: This needs to be tested further with
                templates/topics created
        """
        query = f"g.V().hasLabel('{Team.LABEL}')" + \
            f".inE('{auth.UserAssignedToCoreVertex.LABEL}').outV()" + \
            f".as('member')" + \
            f".out('{auth.UserAssignedToCoreVertex.LABEL}')" + \
            f".project('templatesCount', 'name', 'id', 'member', 'topicsCount')" + \
            f".by(outE('{TeamOwnsTemplate.LABEL}').inV()" + \
            f".hasLabel('{Template.LABEL}').count())" + \
            f".by(values('name'))" + \
            f".by(values('id'))" + \
            f".by(select('member'))" + \
            f".by(outE('{TeamOwnsTemplate.LABEL}').inV()" + \
            f".hasLabel('{Template.LABEL}')" + \
            f".inE('{CoreVertexInheritsFromTemplate.LABEL}').count())"
        result = client.submit(query).all().result()

        # Map of id:team_data for all teams under account;
        # Used to collect members while keeping unique teams
        teams = {}
        for team in result:
            if team["id"] not in teams:
                teams[team["id"]] = {
                    "id": team["id"],
                    "name": team["name"],
                    "templatesCount": team["templatesCount"],
                    "topicsCount": team["topicsCount"],
                    "members": []
                }
            member = {
                "id": team["member"]["id"],
                "email": team["member"]["properties"]["email"][0]["value"],
                "avatarLink": ""  # [TODO]
            }
            if member not in teams[team["id"]]["members"]:
                teams[team["id"]]["members"].append(member)

        return jsonify_response(list(teams.values()), 200)

    @jwt_required
    @auth_permissions.account_held_by_user
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
            user=user.id, team=team.id, role="team_admin")

        # Note: We can just return the logged in user as the only member
        # since there will only be one member upon team creation

        return jsonify_response({
            "name": team.name,
            "id": team.id,
            "members": [{
                "id": user.id,
                "email": user.email,
                "avatarLink": ""  # [TODO]
            }],
            "templatesCount": 0,
            "topicsCount": 0
        }, 201)

core_app.add_url_rule("/account/<account_id>/teams",
                      view_func=ListCreateTeamsView.as_view("teams"))


class ListCreateCoreVertexView(MethodView):
    """ Contains the GET and POST views required for listing and creating
        children CoreVertices in a given Team or CoreVertex
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory()
    def get(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Returns all direct coreVertices under the given parent's
            identifier
        """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404) 

        children = CoreVertexOwnership.get_children(vertex_id, vertex_type)

        schema = CoreVertexListSchema(many=True)
        response = json.loads(schema.dumps(children).data)

        return jsonify_response(response, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory()
    def post(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Creates the core vertex instance of the given type as well as
            and edge from the parent to the created vertex
        """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        data = json.loads(request.data)

        # Confirming the request data schema
        if "title" not in data or "template" not in data:
            return jsonify_response({"error": "Incorrect Schema"}, 400)

        # Confirming that the required template exists on the ROOT of the vertex
        # tree
        template = TeamOwnsTemplate.get_template(
            vertex_type, vertex.id, data["template"])
        if not template:
            return jsonify_response(
                {"error": "Template doesn't exist"}, 404)

        core_vertex = CoreVertex.create(title=data["title"], templateData="{}")
        template_edge = CoreVertexInheritsFromTemplate.create(
            coreVertex=core_vertex.id, template=template.id)
        child_edge = CoreVertexOwnership.create(
            outv_id=vertex_id, inv_id=core_vertex.id,
            inv_label="coreVertex", outv_label=vertex_type)

        response = {
            "id": core_vertex.id,
            "title": core_vertex.title,
            "templateData": core_vertex.templateData,
            "template": {
                "id": template.id,
                "name": template.name,
                "canHaveChildren": template.canHaveChildren
            }
        }
        return jsonify_response(response, 201)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/children/",
                      view_func=ListCreateCoreVertexView
                      .as_view("list_create_core_vertices"))


class RetrieveUpdateCoreVertexView(RetrieveUpdateAPIView):
    """ Container for the DETAIL and UPDATE (full/partial) endpoints
        for CoreVertices;
    """
    serializer_class = CoreVertexDetailSchema
    vertex_class = CoreVertex

    def get_vertex_id(self):
        """ Returns the vertex-id from the parsed url; used in the
            Update mixin
        """
        return request.view_args["vertex_id"]

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="coreVertex",
        direct_allowed_roles=[],  # TODO: Add roles here
        indirect_allowed_roles=["team_admin", "team_lead"])
    def get(self, vertex=None, vertex_id=None, **kwargs):
        """ Returns the object identified by the given vertex id
            - Overridden to add the decorators, and reuse the Vertex
                instance injected through the permission
        """
        self.get_object = lambda: vertex
        return super().get()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="coreVertex",
        direct_allowed_roles=[],  # TODO: Add roles here
        indirect_allowed_roles=["team_admin"])
    def put(self, vertex=None, vertex_id=None, **kwargs):
        """ Full Update endpoint for coreVertices """
        return self.update()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="coreVertex",
        direct_allowed_roles=[],  # TODO: Add roles here
        indirect_allowed_roles=["team_admin"])
    def patch(self, vertex=None, vertex_id=None, **kwargs):
        """ Full Update endpoint for coreVertices """
        return self.update(partial=True)

core_app.add_url_rule("/coreVertex/<vertex_id>",
                      view_func=RetrieveUpdateCoreVertexView
                      .as_view("retrieve_update_core_vertices"))


class ListCreateTemplatesView(MethodView):
    """ Container for the LIST and CREATE Template endpoints
        for a given Team
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def get(self, vertex=None, vertex_type="team", vertex_id=None):
        """ LIST Endpoint for a team's templates """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        query = f"g.V().has('{Team.LABEL}', 'id', '{vertex.id}')" + \
            f".out('{TeamOwnsTemplate.LABEL}').hasLabel('{Template.LABEL}')" + \
            f".project('id', 'name', 'topicsCount')" + \
            f".by(values('id')).by(values('name'))" + \
            f".by(inE('{CoreVertexInheritsFromTemplate.LABEL}').outV()" + \
            f".hasLabel('{CoreVertex.LABEL}').count())"
        result = client.submit(query).all().result()

        return jsonify_response(result, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def post(self, vertex=None, vertex_type="team", vertex_id=None):
        """ CREATE Endpoint for a team's templates """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        data = json.loads(request.data)

        # Basic validation for the input
        if "name" not in data or "canHaveChildren" not in data:
            return jsonify_response({"error": "Invalid schema"}, 400)

        template = Template.create(name=data["name"],
                                   canHaveChildren=data["canHaveChildren"])
        owns_edge = TeamOwnsTemplate.create(team=vertex.id,
                                            template=template.id)

        schema = TemplateSchema()
        response = json.loads(schema.dumps(template).data)

        # Adding the topics count field as 0 since a new template
        # won't have any topics inheriting from it anyways
        response["topicsCount"] = 0

        return jsonify_response(response, 201)

core_app.add_url_rule("/team/<vertex_id>/templates",
                      view_func=ListCreateTemplatesView
                      .as_view("list_create_templates"))


class RetrieveUpdateDeleteTemplatesView(RetrieveUpdateAPIView, DeleteVertexMixin):
    """ Container for the DETAIL and UPDATE (full/partial) endpoints
        for Templates
    """
    serializer_class = TemplateSchema
    vertex_class = Template

    def get_object(self):
        """ Uses the vertex_attribute added to the View to get the
            template
        """
        template = TemplateHasProperty.get_template_with_properties(
            request.view_args["template_id"], request.view_args["vertex_id"])

        return template

    def get_vertex_id(self):
        """ Returns the template-id from the parsed url; used in the
            Update mixin
        """
        return request.view_args["template_id"]

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def get(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Returns the object identified by the given vertex id """
        return super().get()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def put(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Full Update endpoint for Templates """
        return self.update()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def patch(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Full Update endpoint for Templates """
        return self.update(partial=True)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_admin"])
    def delete(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Deletes the given template id """
        return super().delete()

core_app.add_url_rule("/team/<vertex_id>/templates/<template_id>",
                      view_func=RetrieveUpdateDeleteTemplatesView
                      .as_view("retrieve_update_delete_templates"))


class RetrieveUpdateDeleteTeamsView(RetrieveUpdateAPIView, DeleteVertexMixin):
    """ Endpoint which implements the following for teams:
        - GET Detail
        - Update (PUT/PATCH)
        - Delete
    """
    serializer_class = TeamSchema
    vertex_class = Team

    def get_object(self):
        """ Uses the vertex_attribute added to the View to get the
            template
        """
        teams = Team.filter(id=request.view_args["vertex_id"])
        if teams:
            return teams[0]
        return None

    def get_vertex_id(self):
        """ Returns the template-id from the parsed url; used in the
            Update mixin
        """
        return request.view_args["vertex_id"]

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def get(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Returns the object identified by the given vertex id """
        return super().get()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def put(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Full Update endpoint for Templates """
        return self.update()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def patch(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Full Update endpoint for Templates """
        return self.update(partial=True)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_admin"])
    def delete(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Deletes the team identified by the given vertex id """
        return super().delete()

core_app.add_url_rule("/team/<vertex_id>",
                      view_func=RetrieveUpdateDeleteTeamsView
                      .as_view("retrieve_update_delete_teams"))


# [TODO]
class CoreVertexRolesView(MethodView):
    """ Container for all the core vertices' roles endpoint;
            Returns the role owned by the user (current | input) on GET,
            Adds new role on POST
        This view can be used for retrieving and creating new roles for
        a core vertex of types Team | CoreVertex
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

        assigned_role = auth.UserAssignedToCoreVertex.get_user_assigned_role(
            core_vertex.id, target_user.id, inv_label=vertex_type)

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
            target_user_role = auth.UserAssignedToCoreVertex \
                .get_user_assigned_role(
                    core_vertex.id, target_user.id, inv_label=vertex_type)

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
        edge = auth.UserAssignedToCoreVertex \
            .create(user=target_user.id,
                    role=requested_role,
                    inv_label=vertex_type,
                    **{vertex_type: core_vertex.id})

        return jsonify_response({
            "user": target_user.id,
            "team": core_vertex.id,
            "role": edge.role
        }, 200)

# <vertex_type> must be within team | coreVertex
core_app.add_url_rule(
    "/<vertex_type>/<vertex_id>/roles",
    view_func=CoreVertexRolesView.as_view("core_vertex_roles"))
