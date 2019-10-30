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
        """
        teams = Team.get_teams_with_detail(account_id)

        return jsonify_response(teams, 200)

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
    @permissions.core_vertex_permission_decorator_factory(
        direct_allowed_roles=["team_admin", "team_lead", "topic_member"],  # TODO: Add CV Roles here
        indirect_allowed_roles=["team_admin", "team_lead", "topic_member"])
    def get(self, vertex=None, vertex_type=None,
            vertex_id=None, template_id=None):
        """ Returns all direct coreVertices under the given parent's
            identifier
        """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404) 

        children = CoreVertexOwnership.get_children(
            vertex_id, vertex_type, template_id=template_id)

        schema = CoreVertexListSchema(many=True)
        response = json.loads(schema.dumps(children).data)

        return jsonify_response(response, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        direct_allowed_roles=["team_admin", "team_lead"],  # TODO: Add CV roles here
        indirect_allowed_roles=["team_admin", "team_lead"])
    def post(self, vertex=None, vertex_type=None,
             vertex_id=None, template_id=None):
        """ Creates the core vertex instance of the given type as well as
            and edge from the parent to the created vertex
        """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        data = json.loads(request.data)

        # Confirming the request data schema
        if "title" not in data or "templateData" not in data:
            return jsonify_response({"error": "Incorrect Schema"}, 400)

        # Confirming that the required template exists on the ROOT of the vertex
        # tree
        template = TeamOwnsTemplate.get_template(
            vertex_type, vertex.id, template_id)
        if not template:
            return jsonify_response(
                {"error": "Template doesn't exist"}, 404)

        core_vertex = CoreVertex.create(
            title=data["title"], templateData=data["templateData"],
            content=data["content"])
        child_edge = CoreVertexOwnership.create(
            outv_id=vertex_id, inv_id=core_vertex.id,
            inv_label="coreVertex", outv_label=vertex_type)
        template_edge = CoreVertexInheritsFromTemplate.create(
            coreVertex=core_vertex.id, template=template.id)

        response = {
            "id": core_vertex.id,
            "title": core_vertex.title,
            "templateData": core_vertex.templateData,
            "content": core_vertex.content,
            "template": {
                "id": template.id,
                "name": template.name,
                "canHaveChildren": template.canHaveChildren,
                "pilForegroundColor": template.pillForegroundColor,
                "pillBackgroundColor": template.pillBackgroundColor
            }
        }
        return jsonify_response(response, 201)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/templates/<template_id>/nodes",
                      view_func=ListCreateCoreVertexView
                      .as_view("list_create_core_vertices"))


class RetrieveUpdateDeleteCoreVertexView(RetrieveUpdateAPIView, DeleteVertexMixin):
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
        self.get_object = lambda: vertex.get_core_vertex_with_template(
            vertex.id)
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

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="coreVertex",
        direct_allowed_roles=[],  # TODO: Add roles here
        indirect_allowed_roles=["team_admin"])
    def delete(self, vertex=None, vertex_id=None, **kwargs):
        """ Deletes the coreVertex identified by the given vertex id """
        self.get_object = lambda: vertex
        return super().delete()

core_app.add_url_rule("/coreVertex/<vertex_id>",
                      view_func=RetrieveUpdateDeleteCoreVertexView
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

        templates = Template.get_templates_with_details(vertex.id)

        return jsonify_response(templates, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def post(self, vertex=None, vertex_type="team", vertex_id=None):
        """ CREATE Endpoint for a team's templates """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        # Basic validation for the input
        schema = TemplateListSchema()
        data = schema.loads(request.data)
        if data.errors:
            return jsonify_response(data.errors, 400)

        data = json.loads(request.data)

        template = Template.create(
            name=data["name"], canHaveChildren=data["canHaveChildren"],
            pillBackgroundColor=data["pillBackgroundColor"],
            pillForegroundColor=data["pillForegroundColor"])
        template.properties = None  # This is the vertex's `properties` field being Nulled
        owns_edge = TeamOwnsTemplate.create(team=vertex.id,
                                            template=template.id)

        schema = TemplateDetailSchema()
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
    serializer_class = TemplateDetailSchema
    vertex_class = Template

    def get_object(self):
        """ Uses the vertex_attribute added to the View to get the
            template
        """
        template = Template.get_template_with_properties(
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


class CreateTemplatePropertiesView(MethodView):
    """ Endpoint which implements a Creation POST for properties """
    serializer_class = TemplatePropertySchema
    vertex_class = TemplateProperty

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def post(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Creation endpoint for properties """
        schema = self.serializer_class()
        data = schema.loads(request.data)
        if data.errors:
            return jsonify_response(data.errors, 400)

        template = Template.filter(id=template_id)
        if not template:
            return jsonify_response(
                status={"error": "Template does not exist."})
        template = template[0]

        template_prop = TemplateProperty.create(**data.data)
        property_edge = TemplateHasProperty.create(
            templateProperty=template_prop.id, template=template.id)

        return jsonify_response({
            "id": template_prop.id,
            "name": template_prop.name,
            "fieldType": template_prop.fieldType,
            "propertyOptions": template_prop.propertyOptions
        }, 201)

core_app.add_url_rule("/team/<vertex_id>/templates/<template_id>/properties",
                      view_func=CreateTemplatePropertiesView
                      .as_view("create_template_properties"))


class RetrieveUpdateDeleteTemplatePropertiesView(
        RetrieveUpdateAPIView, DeleteVertexMixin):
    """ Endpoint which implements the following for templateProperties:
        - GET Detail
        - Update (PUT/PATCH)
        - Delete
    """
    serializer_class = TemplatePropertySchema
    vertex_class = TemplateProperty

    def get_object(self):
        """ Uses the vertex_attribute added to the View to get the
            templateProperty

            TODO: Change this to retrieve template properties under the given
                template and team only
        """
        template_property = TemplateProperty.filter(id=self.get_vertex_id())
        if template_property:
            return template_property[0]
        return None

    def get_vertex_id(self):
        """ Returns the TempleProperty-id from the parsed url; used in the
            Update mixin
        """
        return request.view_args["property_id"]

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
        """ Full Update endpoint for TempleProperties """
        return self.update()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def patch(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Full Update endpoint for TempleProperties """
        return self.update(partial=True)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_admin"])
    def delete(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Deletes the TempleProperty identified by the given vertex id """
        return super().delete()

core_app.add_url_rule("/team/<vertex_id>/templates/<template_id>"
                      "/properties/<property_id>",
                      view_func=RetrieveUpdateDeleteTemplatePropertiesView
                      .as_view("retrieve_update_delete_template_properties"))


class RetrieveUpdateDeleteTeamsView(RetrieveUpdateAPIView, DeleteVertexMixin):
    """ Endpoint which implements the following for teams:
        - GET Detail
        - Update (PUT/PATCH)
        - Delete
    """
    serializer_class = TeamsDetailSchema
    vertex_class = Team

    def get_object(self):
        """ Uses the vertex_attribute added to the View to get the
            team
        """
        teams = Team.filter(id=request.view_args["vertex_id"])
        if teams:
            return teams[0].get_team_details(teams[0].id)
        return None

    def get_vertex_id(self):
        """ Returns the team-id from the parsed url; used in the
            Update mixin
        """
        return request.view_args["vertex_id"]

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_member", "team_lead", "team_admin"])
    def get(self, vertex=None, vertex_id=None, **kwargs):
        """ Returns the object identified by the given vertex id """
        return super().get()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def put(self, vertex=None, vertex_id=None, **kwargs):
        """ Full Update endpoint for team """
        return self.update()

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def patch(self, vertex=None, vertex_id=None, **kwargs):
        """ Full Update endpoint for team """
        return self.update(partial=True)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_admin"])
    def delete(self, vertex=None, vertex_id=None, **kwargs):
        """ Deletes the team identified by the given vertex id """
        return super().delete()

core_app.add_url_rule("/team/<vertex_id>",
                      view_func=RetrieveUpdateDeleteTeamsView
                      .as_view("retrieve_update_delete_teams"))


class TemplatePropertiesIndexUpdateView(MethodView):
    """ Implements the PUT endpoint for receiving multiple properties
        and updating all of their indexes based on their location
        in the request body array
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def put(self, vertex=None, vertex_id=None, template_id=None, **kwargs):
        """ Endpoint used for update template properties index values """
        data = json.loads(request.data)
        if "properties" not in data:
            return jsonify_response({
                "status": "Properties missing"
            }, 400)

        template = Template.get_template_with_properties(
            template_id, vertex.id)
        prop_ids = [i.id for i in template.properties]
        inp_ids = [i["id"] for i in data["properties"]]

        # Checking that all of the properties given exist under this
        # template
        if not set(prop_ids) == set(inp_ids):
            return jsonify_response({
                "status": "Template Properties not found in template"
            }, 400)

        properties = TemplateProperty.update_properties_index(
            inp_ids)
        schema = TemplatePropertySchema(many=True)
        response = json.loads(schema.dumps(properties).data)

        return jsonify_response(response, 200)

core_app.add_url_rule("/team/<vertex_id>/templates/<template_id>"
                      "/properties_index",
                      view_func=TemplatePropertiesIndexUpdateView
                      .as_view("template_properties_index_update"))


class NodesTreeListView(MethodView):
    """ Returns a list of nodes that are direct children of the given
        node ID along with their closest sub-children
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        direct_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"])
    def get(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Returns a nested tree-view for the given node's children """
        tree = CoreVertexOwnership.get_children_tree(vertex.id)

        schema = TreeViewListSchema(many=True)
        response = json.loads(schema.dumps(tree).data)

        return jsonify_response(response, 200)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/tree_view",
                      view_func=NodesTreeListView
                      .as_view("nodes-tree-list-view"))


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
