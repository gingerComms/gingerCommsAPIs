from flask import Blueprint, request
from flask.views import MethodView
from datetime import datetime as dt
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
from utils.s3_engine import S3Engine


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
        teams = Team.get_teams_with_detail(account_id, get_jwt_identity())

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

        team = Team.create(
            name=data.data["name"]
        )
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
        direct_allowed_roles=["team_admin", "team_lead", "team_member"],  # TODO: Add CV Roles here
        indirect_allowed_roles=["team_admin", "team_lead", "team_member"])
    def get(self, vertex=None, vertex_type=None,
            vertex_id=None, template_id=None):
        """ Returns all corevertices that inherit from the given template id """
        if not vertex:
            return jsonify_response({"error": "Vertex not found"}, 404)

        core_vertices = CoreVertexInheritsFromTemplate \
            .get_all_template_inheritors(template_id)

        schema = CoreVertexListSchema(many=True)
        response = json.loads(schema.dumps(core_vertices).data)

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
                "canHaveChildren": True if template.canHaveChildren == "True" else False,
                "pillForegroundColor": template.pillForegroundColor,
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
        self.get_object = lambda: vertex.get_core_vertex_with_details(
            vertex.id, get_jwt_identity())
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


class ChangeCoreVertexParentView(MethodView):
    """ Contains the endpoint used for changing the parent of a given
        core vertex
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="coreVertex",
        direct_allowed_roles=[],  # TODO: Add roles here
        indirect_allowed_roles=["team_admin", "team_lead"])
    def put(self, vertex=None, vertex_id=None, **kwargs):
        """ Changes the parent of the given core vertex after removing existing
            parent edge
        """
        data = json.loads(request.data)
        if "newParent" not in data:
            return jsonify_response({
                "status": "New parent not specified"
            }, 400)
        # Moving all of the direct children to the existing parent IF
        # the node has been made a child of one of it's older children
        existing_data_query = f"g.V().has('id', '{vertex.id}')" + \
            f".project('existingParent', 'newParent', 'directChildren')" + \
            f".by(inE('{CoreVertexOwnership.LABEL}').outV())" + \
            f".by(until(has('id', '{data['newParent']}').or().loops().is(30))" + \
            f".repeat(out('{CoreVertexOwnership.LABEL}')).fold())" + \
            f".by(outE('{CoreVertexOwnership.LABEL}').inV().fold())"
        existing_data = client.submit(existing_data_query).all().result()[0]
        old_parent_id = existing_data["existingParent"]["id"]
        existing_direct_children = [CoreVertex.vertex_to_instance(i) for
                                    i in existing_data["directChildren"]]
        new_parent_is_child = len(existing_data["newParent"]) >= 1

        print("Existing Data", existing_data)

        # Updating first level children to have an edge to the old parent
        # if the new parent is a sub-child of the moved node
        if new_parent_is_child:
            print("NEW PARENT IS CHILD")
            children_ids = ",".join(
                [f"'{i.id}'" for i in existing_direct_children])
            children_relocate_query = f"g.V().has('id', within({children_ids}))" + \
                f".inE('{CoreVertexOwnership.LABEL}').drop()"
            client.submit(children_relocate_query).all().result()

            children_relocate_query = f"g.V().has('id', '{old_parent_id}')"
            for index, child in enumerate(existing_direct_children):
                children_relocate_query += f".addE('{CoreVertexOwnership.LABEL}')" + \
                    f".to(g.V().has('id', '{child.id}'))"
                children_relocate_query += ".outV()"
            client.submit(children_relocate_query).all().result()

        # Removing the existing parent edge, and adding the new edge
        query = f"g.V().has('id', '{vertex.id}').as('node')" + \
            f".inE('{CoreVertexOwnership.LABEL}').as('existingEdge')" + \
            f".inV().addE('{CoreVertexOwnership.LABEL}')" + \
            f".from(g.V().has('id', '{data['newParent']}'))" + \
            f".select('existingEdge').drop()"
        res = client.submit(query).all().result()

        return jsonify_response({
            "status": "Success"
        }, 200)

core_app.add_url_rule("/coreVertex/<vertex_id>/change_parent",
                      view_func=ChangeCoreVertexParentView
                      .as_view("change_core_vertex_parent"))


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
        tree = CoreVertexOwnership.get_children_tree(
            vertex.id, get_jwt_identity())

        schema = TreeViewListSchema(many=True)
        response = json.loads(schema.dumps(tree).data)

        return jsonify_response(response, 200)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/tree_view",
                      view_func=NodesTreeListView
                      .as_view("nodes-tree-list-view"))


class ListCreateNodesAssignedUsersView(MethodView):
    """ Container for endpoints for listing assigned users and
        assigning new users to a given coreVertex
    """
    allowed_roles = {
        "team": ["team_member", "team_admin", "team_lead"],
        "coreVertex": ["cv_member", "cv_admin", "cv_lead"]
    }

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def get(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Returns all users with their roles currently assigned
            to the given core vertex
        """
        members = auth.UserAssignedToCoreVertex.get_members(
            vertex_type, vertex_id)

        return jsonify_response(members, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_admin", "team_lead",
                              "cv_admin", "cv_lead"])
    def post(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Endpoint for assigning a particular role for a node to
            a user
        """
        current_user = get_jwt_identity()
        data = json.loads(request.data)
        if "user" not in data or "role" not in data:
            return jsonify_response({
                "status": "The `user` and `role` must be provided."
            }, 400)
        if data["role"] not in self.allowed_roles[vertex_type]:
            return jsonify_response({
                "status": f"Roles must be in {self.allowed_roles[vertex_type]}"
            }, 400)

        target_user = auth.User.filter(email=data["user"])
        if not target_user:
            return jsonify_response({
                "status": f"User with provided email doesn't exist."
            }, 404)
        target_user = target_user[0]

        existing_role = auth.UserAssignedToCoreVertex.get_user_assigned_role(
            vertex.id, target_user.id, inv_label=vertex_type)
        if existing_role:
            return jsonify_response({
                "status": f"User already has a role for this node"
            }, 400)

        edge = auth.UserAssignedToCoreVertex.create(
            outv_id=target_user.id, outv_label="user",
            inv_id=vertex.id, inv_label=vertex_type, role=data["role"])
        user = auth.User.filter(id=current_user)[0]

        return jsonify_response({
            "role": edge.role,
            "id": target_user.id,
            "email": target_user.email,
            "avatarLink": ""
        }, 201)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/assignees",
                      view_func=ListCreateNodesAssignedUsersView
                      .as_view("nodes-assigned-users"))


class UpdateDeleteNodesAssignedUsers(MethodView):
    """ Contains the PUT and DELETE method for assigned users
        for a given node
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_admin", "team_lead",
                              "cv_admin", "cv_lead"])
    def put(self, vertex=None, vertex_type=None,
            vertex_id=None, assignee_id=None):
        """ Endpoint for updating a user's role for a given node """
        target_user = auth.User.filter(id=assignee_id)
        if not target_user:
            return jsonify_response({
                "status": f"User with provided ID doesn't exist"
            }, 404)
        target_user = target_user[0]

        data = json.loads(request.data)
        if "role" not in data:
            return jsonify_response({
                "status": f"The `role` parameter must be provided"
            }, 400)

        current_user_role = auth.UserAssignedToCoreVertex \
            .get_user_assigned_role(vertex.id, get_jwt_identity(),
                                    inv_label=vertex_type)
        target_user_role = auth.UserAssignedToCoreVertex \
            .get_user_assigned_role(vertex.id, target_user.id,
                                    inv_label=vertex_type)
        if "admin" in data["role"] and "lead" in current_user_role.role or \
                "admin" in target_user_role.role and \
                "lead" in current_user_role.role:
            return jsonify_response({
                "status": f"Action not permitted"
            }, 403)

        # Updating the role for the target user
        query = f"g.V().has('{auth.User.LABEL}', 'id', '{target_user.id}')" + \
            f".outE('{auth.UserAssignedToCoreVertex.LABEL}').as('e')" + \
            f".inV().has('{vertex.LABEL}', 'id', '{vertex.id}')" + \
            f".select('e').property('role', '{data['role']}')"
        result = client.submit(query).all().result()

        return jsonify_response({
            "role": data['role']
        }, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_admin", "team_lead",
                              "cv_admin", "cv_lead"])
    def delete(self, vertex=None, vertex_type=None,
               vertex_id=None, assignee_id=None):
        """ Endpoint for removing an assigned user edge for a given
            node/user pair
        """
        target_user = auth.User.filter(id=assignee_id)
        if not target_user:
            return jsonify_response({
                "status": f"User with provided ID doesn't exist"
            }, 404)
        target_user = target_user[0]

        edge = auth.UserAssignedToCoreVertex.filter(
            outv_label="user", inv_label=vertex_type,
            outv_id=target_user.id, inv_id=vertex.id)
        if not edge:
            return jsonify_response({
                "status": f"User doesn't have any role for this node"
            }, 400)
        edge = edge[0]
        edge.delete()

        return jsonify_response({
            "status": "Successfully deleted!"
        })

core_app.add_url_rule("/<vertex_type>/<vertex_id>/assignees/<assignee_id>",
                      view_func=UpdateDeleteNodesAssignedUsers
                      .as_view("nodes-assigned-users-detail"))


class ListCreateFavoriteNodes(MethodView):
    """ Container for the LIST and CREATE endpoints for favorite nodes """
    vertex_types = {
        "team": Team,
        "coreVertex": CoreVertex
    }

    @jwt_required
    def get(self):
        """ Returns all of the user's favorite nodes that he has access to
            UNTESTED
        """
        favorite_nodes = UserFavoriteNode.get_favorite_nodes(
            get_jwt_identity())

        schema = GenericNodeSchema(many=True)
        response = json.loads(schema.dumps(favorite_nodes).data)

        return jsonify_response(response, 200)

    @jwt_required
    def post(self):
        """ Endpoint used for favoriting a node for the currently
            authenticated user
        """
        user_id = get_jwt_identity()
        data = json.loads(request.data)
        if "nodeId" not in data or "nodeType" not in data:
            return jsonify_response({
                "error": "`nodeId` or `nodeType` not provided."
            }, 400)

        vertex_class = self.vertex_types[data["nodeType"]]
        vertex = vertex_class.filter(id=data["nodeId"])
        if not vertex:
            return jsonify_response({
                "error": "Node does not exist."
            }, 404)
        vertex = vertex[0]

        existing_edge = UserFavoriteNode.filter(
            outv_id=user_id, inv_id=vertex.id,
            outv_label="user", inv_label=data["nodeType"])
        if existing_edge:
            return jsonify_response({
                "error": "Favorite node already exists."
            }, 400)

        vertex_roles = vertex.get_user_permissions(user_id)
        direct_vertex_role = vertex_roles["direct_role"]
        indirect_vertex_roles = vertex_roles["indirect_roles"]

        if direct_vertex_role or [i for i in indirect_vertex_roles
                                  if "lead" in i or "admin" in i]:
            edge = UserFavoriteNode.create(
                outv_id=user_id, inv_id=vertex.id,
                outv_label="user", inv_label=data["nodeType"])

            schema = GenericNodeSchema()
            response = json.loads(schema.dumps(vertex).data)

            return jsonify_response(response, 201)

        return jsonify_response({
            "error": "User does not have access to node"
        }, 403)

core_app.add_url_rule("/favorite_nodes",
                      view_func=ListCreateFavoriteNodes
                      .as_view("list-create-favorite-nodes"))


class DestroyFavoriteNodesView(MethodView):
    """ Provides a DELETE endpoint for favorite node edges """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_admin", "team_lead", "team_member"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_admin", "team_lead", "team_member"
                              "cv_admin", "cv_lead", "cv_member"])
    def delete(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Removes the favorite node edge between the user and the
            given vertex
        """
        user_id = get_jwt_identity()

        edge = UserFavoriteNode.filter(
            outv_id=user_id, inv_id=vertex.id,
            outv_label="user", inv_label=vertex_type)
        if not edge:
            return jsonify_response({
                "error": "Edge does not exist."
            }, 404)

        edge = edge[0]
        edge.delete()

        return jsonify_response({
            "status": "Deleted Successfully"
        }, 200)

core_app.add_url_rule("/favorite_nodes/<vertex_type>/<vertex_id>",
                      view_func=DestroyFavoriteNodesView
                      .as_view("destroy-favorite-nodes"))


class ListCreateNodeMessagesView(MethodView):
    """ Container for list and create endpoints for node-messages """

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def get(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Returns all users with their roles currently assigned
            to the given core vertex
        """
        user_id = get_jwt_identity()

        # ISO Format times for filtering 10 before or after
        before = request.args.get("before")
        after = request.args.get("after")

        last_checked = UserLastCheckedMessage \
            .get_last_checked_time(user_id, vertex.id)
        if not before and (last_checked or after):
            since = last_checked.time if not after else after
            messages = Message.list_messages(
                vertex.id,
                start=0, end=10,
                filter_date=dt.strptime(since, "%Y-%m-%dT%H:%M:%S.%f"),
                date_filter="gt" if after else "gte")
        elif before:
            messages = Message.list_messages(
                vertex.id,
                start=-10, end=None,
                filter_date=dt.strptime(before, "%Y-%m-%dT%H:%M:%S.%f"),
                date_filter="lt")
        # If the user hasn't checked the messages at all, return the last
        # page
        else:
            messages = Message.list_messages(vertex.id, start=-10, end=None)
        # Updating the last read time for the user to the latest message
        # loaded - IF it's newer than the current last read value
        if not before and len(messages) > 0:
            last_checked_data = {
                "outv_label": "user",
                "inv_label": vertex_type,
                "outv_id": user_id,
                "inv_id": vertex.id,
                "time": messages[-1].sent_at
            }
            if last_checked is not None:
                last_checked.delete()
            UserLastCheckedMessage.create(**last_checked_data)

        schema = MessageListSchema(many=True)
        response = json.loads(schema.dumps(messages).data)

        return jsonify_response(response, 200)

    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def post(self, vertex=None, vertex_type=None, vertex_id=None):
        """ Creation endpoint used for adding new messages against a node """
        data = json.loads(request.data)
        user_id = get_jwt_identity()
        user = auth.User.filter(id=user_id)[0]

        schema = MessageListSchema()
        errors = schema.loads(request.data).errors
        if errors:
            return jsonify_response({"errors": errors}, 400)

        sent_at = dt.now().isoformat()
        message = Message.create(text=data["text"], sent_at=sent_at)
        author_edge = UserSentMessage.create(user=user_id, message=message.id)
        node_edge = NodeHasMessage.create(
            outv_label=vertex_type, inv_label="message",
            outv_id=vertex.id, inv_id=message.id)

        # Updating last checked
        last_checked = UserLastCheckedMessage \
            .get_last_checked_time(user_id, vertex.id)
        if last_checked:
            last_checked.delete()
        last_checked_edge = UserLastCheckedMessage.create(
            outv_label="user", inv_label=vertex_type,
            outv_id=user_id, inv_id=vertex.id, time=sent_at)

        response = json.loads(schema.dumps(message).data)
        return jsonify_response({
            "id": message.id,
            "text": message.text,
            "sent_at": sent_at,
            "author": {
                "id": user.id,
                "fullName": user.fullName,
                "email": user.email,
                "username": user.username
            }
        }, 201)

core_app.add_url_rule("/<vertex_type>/<vertex_id>/messages",
                      view_func=ListCreateNodeMessagesView
                      .as_view("list-create-node-messages"))


class InboxMessagesListView(MethodView):
    """ Contains for the GET endpoint which returns a list of nodes +
        last message details for the nodes that the user has in his
        favorites
    """
    @jwt_required
    def get(self):
        """ Returns a list of nodes + last message details for the nodes
            the user has in his favorites
        """
        user_id = get_jwt_identity()
        nodes = UserFavoriteNode.get_inbox_nodes(user_id)

        schema = InboxNodesSchema(many=True)
        response = json.loads(schema.dumps(nodes).data)

        return jsonify_response(response, 200)

core_app.add_url_rule("/inbox_nodes",
                      view_func=InboxMessagesListView
                      .as_view("list-inbox-nodes"))


class TemplateNodesIndexUpdateView(MethodView):
    """ Contains the Update view which takes an array of nodes with their
        IDs and templateData as input and updates the entire array
        in the database (for index maintainence)
    """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        overwrite_vertex_type="team",
        direct_allowed_roles=["team_lead", "team_admin"])
    def put(self, vertex=None, template_id=None, vertex_id=None, **kwargs):
        """ Updates the templateData property of all received
            nodes
            Format: { nodes: [nodeId: templateDataString...] }
        """
        data = json.loads(request.data)
        if "nodes" not in data:
            return jsonify_response({
                "status": "Nodes missing"
            }, 400)

        CoreVertex.bulk_update_template_data(data["nodes"])

        return jsonify_response({
            "status": "Success"
        }, 200)

core_app.add_url_rule("/team/<vertex_id>/templates/<template_id>"
                      "/nodes_index",
                      view_func=TemplateNodesIndexUpdateView
                      .as_view("template_nodes_index_update"))


class GeneratePresignedS3PostView(MethodView):
    """ Returns a presigned POST requesst for the provided filename """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def post(self, vertex=None, vertex_type=None, vertex_id=None, property_id=None):
        """ Generates and returns a presigned POST for the provided
            teamID/propertyID/fileName key
        """
        filename = request.form["filePath"]
        engine = S3Engine()
        key = f"{vertex.id}/{property_id}/{filename}"
        signed_url = engine.generate_presigned_post(key)

        return jsonify_response({
            "postEndpoint": signed_url["url"],
            "signature": signed_url["fields"]
        })

core_app.add_url_rule("/<vertex_type>/<vertex_id>/<property_id>/generate_s3_post",
                      view_func=GeneratePresignedS3PostView
                      .as_view("generate-presigned-post"))


class GeneratePresignedS3GetView(MethodView):
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def post(self, vertex=None, vertex_type=None, vertex_id=None, property_id=None):
        """ Generates and returns a presigned GET url for the provided file """
        data = json.loads(request.data)
        filename = data["filePath"]
        engine = S3Engine()
        key = f"{vertex.id}/{property_id}/{filename}"

        return jsonify_response({
            "url": engine.generate_presigned_get_url(key)
        })

core_app.add_url_rule("/<vertex_type>/<vertex_id>/<property_id>/generate_s3_get",
                      view_func=GeneratePresignedS3GetView
                      .as_view("generate-presigned-get"))

class DeleteS3FileView(MethodView):
    """ Container for the S3 file deletion endpoint """
    @jwt_required
    @permissions.core_vertex_permission_decorator_factory(
        indirect_allowed_roles=["team_member", "team_admin", "team_lead"],  # TODO: Add CV roles here
        direct_allowed_roles=["team_member", "team_admin", "team_lead",
                              "cv_member", "cv_admin", "cv_lead"])
    def post(self, vertex=None, vertex_type=None, vertex_id=None, property_id=None):
        """ Deletes the provided file in the property """
        data = json.loads(request.data)

        filename = data["filePath"]
        engine = S3Engine()
        key = f"{vertex.id}/{property_id}/{filename}"
        signed_url = engine.delete_file(key)

        return jsonify_response({
            "status": "Success"
        })


core_app.add_url_rule("/<vertex_type>/<vertex_id>/<property_id>/delete_file",
                      view_func=DeleteS3FileView
                      .as_view("delete-s3-file"))
