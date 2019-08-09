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
        "title": str
    }


class TemplateProperty(Vertex):
    """ Represents an input "field" added by a user in a template """
    LABEL = "property"
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
        "fields": str,  # User defined JSON string sent in from the frontend
        "canHaveChildren": bool
    }


class CoreVertexOwnership(Edge):
    """ Represents a Parental Relationship between CoreVertices;
        Teams can own CoreVertices and CoreVertices can own other CoreVertices
        if the Template they inherit from has the "hasChildren" bool set to
        True
    """
    LABEL = "owns"
    # Both of these can be overridden during init (team | coreVertex)
    OUTV_LABEL = "coreVertex"
    INV_LABEL = "coreVertex"
    properties = {}


    @classmethod
    def select_under_parent(cls, parent_id, queried_vertex_id):
        """ Searches for the given vertex id under the given parent id
            under the parent in the tree (children and subchildren included
            in the search)
            Mainly used for asserting that the queried vertex is a child of the
            parent
            TODO: Perhaps include permissions check as a part of this function
            later
        """
        query = f"g.V().has('id', '{parent_id}')" + \
            f".repeat(out('owns')).until(has('id', '{queried_vertex_id}'))"
        result = client.submit(query).all().result()

        if not result:
            raise None

        return CoreVertex.vertex_to_instance(result[0])
