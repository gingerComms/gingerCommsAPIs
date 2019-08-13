from db.engine import Vertex, Edge, client
from settings import DATABASE_SETTINGS


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


class Team(Vertex):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (coreVertices) against other users under this Team
    """
    LABEL = "team"
    properties = {
        "name": str
    }


class CoreVertex(Vertex):
    """ Represents a CoreVertex instance that is based off of (inherits from)
        a template, and is under a tree with a "Team" as the Root
    """
    LABEL = "coreVertex"
    properties = {
        "title": str,
        "templateData": str
    }


class TemplateProperty(Vertex):
    """ Represents an input "field" added by a user in a template """
    LABEL = "templateProperty"
    properties = {
        "name": str,
        "fieldType": str
    }


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

    @classmethod
    def get_template_with_properties(cls, template_id, parent_team_id=None):
        """ Returns the template and the template properties belonging to it
            in a single query
        """
        query_suffix = f".has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".as('template').out('{cls.LABEL}').as('property')" + \
            f".select('template', 'property')"

        query = f"g.V()"
        if parent_team_id is not None:
            query += f".has('{Team.LABEL}', 'id', '{parent_team_id}')" + \
                f".out('{TeamOwnsTemplate.LABEL}')"

        res = client.submit(query+query_suffix).all().result()

        if not res:
            return None

        template = Template.vertex_to_instance(res[0]["template"])
        template.properties = [
            TemplateProperty.vertex_to_instance(i["property"]) for i in res]

        return template


class CoreVertexOwnership(Edge):
    """ Represents a Parental Relationship between CoreVertices;
        Teams can own CoreVertices and CoreVertices can own other CoreVertices
        if the Template they inherit from has the "hasChildren" bool set to
        True
    """
    LABEL = "owns"
    # This can be overridden during init (team | coreVertex)
    OUTV_LABEL = "team"
    INV_LABEL = CoreVertex.LABEL
    properties = {}

    @classmethod
    def get_children(cls, parent_id, parent_type):
        """ Returns all DIRECT children coreVertices under the given
            parent
        """
        query = f"g.V().has('{parent_type}', 'id', '{parent_id}')" + \
            f".out('{cls.LABEL}').hasLabel('{CoreVertex.LABEL}')"
        result = client.submit(query).all().result()

        return [CoreVertex.vertex_to_instance(i) for i in result]