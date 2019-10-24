from db.engine import Vertex, Edge, client
from settings import DATABASE_SETTINGS
from db.exceptions import (
    CustomValidationFailedException,
    ObjectCanNotBeDeletedException
)
import auth
import re


class TeamOwnsTemplate(Edge):
    """ Represents an Ownership Relationship (One to Many) between a
        Team to a Template.
        All children and sub-children of a team can "use" (Edge) a Template
        owned by the Team
    """
    LABEL = "owns"
    OUTV_LABEL = "team"
    INV_LABEL = "template"
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides validation to confirm that:
            1) A template is only ever owned by one team at a time
        """
        existing_edge_q = f"g.V().has('{cls.INV_LABEL}', 'id', '{inv_id}')" + \
            f".inE('owns')"
        existing_edge = client.submit(existing_edge_q).all().result()
        if existing_edge:
            raise CustomValidationFailedException(
                "Template can only be owned by a single template at a time!")

        return data

    @classmethod
    def all_team_templates(cls, team_id):
        """ Return all templates under the given team """
        query = f"g.V().has('{Team.LABEL}', 'id', '{team_id}')" + \
            f".out('{cls.LABEL}')"
        results = client.submit(query).all().result()

        return [Template.vertex_to_instance(i) for i in results]

    @classmethod
    def get_template(cls, vertex_type, vertex_id, template_id):
        """ Returns the template owned by the given:
                "Team" if the vertex_type is a `team`, or
                "CoreVertex's Root Level Team" if the vertex_type is a
                    `coreVertex`
        """
        base_template_query = f".out('{TeamOwnsTemplate.LABEL}')" + \
            f".has('id', '{template_id}')"

        if vertex_type == "team":
            # If this node is the team (root), we can just check if it has an
            # outgoing edge to this template
            query = f"g.V().has('{Team.LABEL}', 'id', '{vertex_id}')" + \
                base_template_query
        else:
            # Otherwise, we have to find the Team (Root) for this CoreVertex,
            # and then check if that team has the template
            query = f"g.V().has('{CoreVertex.LABEL}', 'id', '{vertex_id}')" + \
                f".repeat(__.in('{CoreVertexOwnership.LABEL}'))" + \
                f".until(__.hasLabel('{Team.LABEL}'))" + \
                base_template_query

        template = client.submit(query).all().result()
        if not template:
            return None
        return Template.vertex_to_instance(template[0])


class CoreVertexInheritsFromTemplate(Edge):
    """ Represents a "inheritsFrom" Relationship between a CoreVertex
        and a Template (owned (Edge) by the CoreVertice's Root Team)
    """
    LABEL = "inheritsFrom"
    OUTV_LABEL = "coreVertex"
    INV_LABEL = "template"
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides custom validation to confirm that:
            1) A Core Vertex only inherits from one template at a time and
            2) Core Vertex only inherits froom a template owned by the vertex's
                team [TODO]
        """
        # Verification for [1]
        existing_template_query = \
            f"g.V().has('{cls.OUTV_LABEL}', 'id', '{outv_id}')" + \
            f".out('{cls.LABEL}')"
        existing_template = client.submit(
            existing_template_query).all().result()
        if existing_template:
            raise CustomValidationFailedException(
                "A CoreVertex can only inherit from a single Template "
                "at a time")

        # Verification for [2]
        team_template_query = \
            f"g.V().has('{CoreVertex.LABEL}', 'id', '{outv_id}')" + \
            f".until(hasLabel('{Team.LABEL}'))" + \
            f".repeat(__.in('{CoreVertexOwnership.LABEL}')).emit()" + \
            f".out('{TeamOwnsTemplate.LABEL}')" + \
            f".has('{Template.LABEL}', 'id', '{inv_id}')"
        template_exists = client.submit(
            team_template_query).all().result()
        if not template_exists:
            raise CustomValidationFailedException(
                "The provided template either doesn't exist, or is not owned"
                "by the same team as the CoreVertex")

        return data


class Team(Vertex):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (coreVertices) against other users under this Team
    """
    LABEL = "team"
    properties = {
        "name": str
    }

    def get_user_permissions(self, user_id):
        """ Returns the roles assigned to the given user for this
            Team
        """
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".inE('{auth.UserAssignedToCoreVertex.LABEL}').as('e')" + \
            f".outV().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".select('e')"
        result = client.submit(query).all().result()

        return auth.UserAssignedToCoreVertex.edge_to_instance(result[0]).role \
            if result else None

    def get_members(self):
        """ Returns a list of members (id, email, avatarLink) that
            are assigned to this team
        """
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".inE('{auth.UserAssignedToCoreVertex.LABEL}').outV()"
        result = client.submit(query).all().result()

        members = [auth.User.vertex_to_instance(i) for i in result]
        return [{
            "id": member.id,
            "email": member.email,
            "avatarLink": "",  # [TODO]
        } for member in members]

    @classmethod
    def get_team_details(cls, team_id):
        """ Returns a Team object containing all of the fields required
            for the team-details endpoint(s) including:
                name, id, templates
            NOTE: This will raise an exception if the ID doesn't exist
        """
        query = f"g.V().as('team').has('{cls.LABEL}', 'id', '{team_id}')" + \
            f".fold().project('team', 'templates').by(unfold())" + \
            f".by(unfold().out('{TeamOwnsTemplate.LABEL}')" + \
            f".hasLabel('{Template.LABEL}').fold())"
        result = client.submit(query).next()[0]

        team = Team.vertex_to_instance(result["team"])
        team.templates = [
            Template.vertex_to_instance(i) for i in result["templates"]]

        return team


class CoreVertex(Vertex):
    """ Represents a CoreVertex instance that is based off of (inherits from)
        a template, and is under a tree with a "Team" as the Root
    """
    LABEL = "coreVertex"
    properties = {
        "title": str,
        "templateData": str
    }

    def get_user_permissions(self, user_id):
        """ Returns all roles assigned to the given user for this CoreVertex
            as a dictionary of
            {direct_role: <edge>, indirect_roles: [edges...]}
        """
        # This will return all of the permissions the user has for all of the
        # vertices in this vertex's path to the root
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".until(__.hasLabel('{Team.LABEL}'))" + \
            f".repeat(__.in('{CoreVertexOwnership.LABEL}')).path()" + \
            f".unfold().inE('{auth.UserAssignedToCoreVertex.LABEL}')" + \
            f".as('e').outV().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".select('e')"
        results = client.submit(query).all().result()

        roles = {
            "indirect_roles": [],
            "direct_role": None
        }

        for edge in results:
            if edge["inV"] == self.id:
                roles["direct_role"] = auth.UserAssignedToCoreVertex \
                    .edge_to_instance(edge).role
            else:
                roles["indirect_roles"].append(
                    auth.UserAssignedToCoreVertex.edge_to_instance(edge).role)

        return roles


class TemplateProperty(Vertex):
    """ Represents an input "field" added by a user in a template """
    LABEL = "templateProperty"
    properties = {
        "name": str,
        "fieldType": str,
        # Contains certain options (list etc.) for the property; JSON str
        "propertyOptions": str,
        "value": str  # This is a code-friendly name for the property
    }

    @classmethod
    def create(cls, value=None, **data):
        """ Valuefies the value to make it code friendly before passing
            it on to the regular create method
        """
        if value:
            value = re.sub(r"[^a-zA-Z0-9]", "", value)
        return super().create(value=value, **data)


class Template(Vertex):
    """ Represents a template that has a user-defined set of custom "fields"
        that act as "templateProperties" on a CoreVertex that
        have, the root as a Team
    """
    LABEL = "template"
    properties = {
        "name": str,
        "canHaveChildren": bool
    }

    @classmethod
    def update(cls, validated_data={}, vertex_id=None):
        """ Updates the template through the base `update` method, as well
            as added functionality for adding (DROPPING + RECREATING) the
            properties
        """
        template_properties = validated_data.pop("properties", [])

        template = super().update(validated_data=validated_data, vertex_id=vertex_id)

        # Dropping all template properties and recreating them
        if template_properties:
            drop_query = f"g.V().has('{cls.LABEL}', 'id', '{vertex_id}')" + \
                f".out('{TemplateHasProperty.LABEL}').drop()"
            client.submit(drop_query)

            # Recreating the provided template_properties
            create_query = "g.V()" + \
                f".has('{Template.LABEL}', 'id', '{template.id}').as('t')"
            for prop in template_properties:
                # Vertex Create + partition key query
                create_query += f".addV('{TemplateProperty.LABEL}')" + \
                    f".property('{DATABASE_SETTINGS['partition_key']}', " + \
                    f"'{TemplateProperty.LABEL}')"
                # A property call for each field
                for field, field_type in TemplateProperty.properties.items():
                    create_query += f".property('{field}', '{prop[field]}')"
                # The edge linking the template to the property
                create_query += f".addE('{TemplateHasProperty.LABEL}')" + \
                    ".from('t')"
            # Selecting all created properties at the end of the query
            create_query += f".outV().out('{TemplateHasProperty.LABEL}')"

            res = client.submit(create_query).all().result()
            template.properties = [
                TemplateProperty.vertex_to_instance(i) for i in res]

        return template

    @classmethod
    def get_template_with_properties(cls, template_id, parent_team_id=None):
        """ Returns the template and the template properties belonging to it
            in a single query
        """
        query = "g.V()"
        # Prepending a team query if the team id arg is provided
        if parent_team_id:
            query += f".has('{Team.LABEL}', 'id', " + \
                f"'{parent_team_id}').out('{TeamOwnsTemplate.LABEL}')"
        query += f".has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".fold().project('template', 'properties').by(unfold())" + \
            f".by(unfold().out('{TemplateHasProperty.LABEL}').fold())"

        try:
            # This raises a 597 error if there's nothing found
            res = client.submit(query).all().result()
        except:
            return None

        template = Template.vertex_to_instance(res[0]["template"])
        template.properties = [
            TemplateProperty.vertex_to_instance(i) for i
            in res[0]["properties"]]

        return template


class TemplateHasProperty(Edge):
    """ Represents an outward edge from a Template to a TemplateProperty,
        identifying that a Template has a particular Property
    """
    LABEL = "hasProperty"
    OUTV_LABEL = Template.LABEL
    INV_LABEL = TemplateProperty.LABEL
    properties = {}

    @classmethod
    def get_template_properties(cls, template_id):
        """ Returns all TemplateProperties belonging to the given template """
        query = f"g.V().has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".out('{cls.LABEL}')"

        res = client.submit(query).all().result()

        return [TemplateProperty.vertex_to_instance(i) for i in res]


class CoreVertexOwnership(Edge):
    """ Represents a Parental Relationship between CoreVertices;
        Teams can own CoreVertices and CoreVertices can own other CoreVertices
        if the Template they inherit from has the "hasChildren" bool set to
        True
    """
    LABEL = "owns"
    # This can be overridden during create (team | coreVertex)
    OUTV_LABEL = "team"
    INV_LABEL = CoreVertex.LABEL
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides validation to confirm that
            1) A coreVertex is only ever owned by one team/coreVertex at a time
            2) A coreVertex can only be owned by a coreVertex whose Template
                 has the canHaveChildren property set to True
        """
        existing_edge_q = f"g.V().has('{inv_label}', 'id', '{inv_id}')" + \
            f".inE('owns')"
        existing_edge = client.submit(existing_edge_q).all().result()
        if existing_edge:
            raise CustomValidationFailedException(
                "CoreVertex can only be owned by a single parent at a time!")

        # Checking for the template's canHaveChildren property if the
        # parent is a coreVertex
        if outv_label == "coreVertex":
            parent_template_query = \
                f"g.V().has('{outv_label}', 'id', '{outv_id}')" + \
                f".out('{CoreVertexInheritsFromTemplate.LABEL}')"
            parent_template = Template.vertex_to_instance(
                client.submit(parent_template_query).all().result()[0])
            if parent_template.canHaveChildren != "True":
                raise CustomValidationFailedException(
                    "CoreVertex can only be owned by a CoreVertex that has"
                    " it's template's canHaveChildren property set to `true`!")

        return data

    @classmethod
    def get_children(cls, parent_id, parent_type, template_id=None):
        """ Returns all DIRECT children coreVertices under the given
            parent
        """
        query = f"g.V().has('{parent_type}', 'id', '{parent_id}')" + \
            f".out('{cls.LABEL}').hasLabel('{CoreVertex.LABEL}')"

        if template_id:
            query += f".as('cv')" + \
                f".out('{CoreVertexInheritsFromTemplate.LABEL}')" + \
                f".has('id', '{template_id}').select('cv')"

        result = client.submit(query).all().result()

        return [CoreVertex.vertex_to_instance(i) for i in result]

    @classmethod
    def get_root(cls, core_vertex_id):
        """ Returns the team vertex at the base of this core-vertex
            ownership tree
            [UNTESTED]
        """
        query = \
            f"g.V().has('{CoreVertex.LABEL}', 'id', '{core_vertex_id}')" + \
            f".until(hasLabel('{Team.LABEL}')).repeat(out('{cls.LABEL}'))"

        team = client.submit(query).all().result()[0]
        return Team.vertex_to_instance(team)
