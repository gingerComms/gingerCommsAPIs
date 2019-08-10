from db.engine import Vertex, Edge, client


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
    fields = {
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


class TemplateHasProperty(Edge):
    """ Represents an outward edge from a Template to a TemplateProperty,
        identifying that a Template has a particular Property
    """
    LABEL = "hasProperty"
    OUTV_LABEL = "template"
    INV_LABEL = "templateProperty"
    properties = {}


class CoreVertexOwnership(Edge):
    """ Represents a Parental Relationship between CoreVertices;
        Teams can own CoreVertices and CoreVertices can own other CoreVertices
        if the Template they inherit from has the "hasChildren" bool set to
        True
    """
    LABEL = "owns"
    # This can be overridden during init (team | coreVertex)
    OUTV_LABEL = "team"
    INV_LABEL = "coreVertex"
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
