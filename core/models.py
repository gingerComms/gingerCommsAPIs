from db.engine import Vertex, Edge, client


class Team(Vertex):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (projects/topics etc.) against other users under this Team
    """
    LABEL = "team"
    properties = {
        "name": str
    }


class Project(Vertex):
    """ Represents a Project instance that that can serve as a parent to
        other Nodes (Project/Topics), and have it's own `UserAssignedToX`
        incoming edge with Users
    """
    LABEL = "project"
    properties = {
        "title": str,
        "description": str,
        "status": int,
        "date_created": str,
        "due_date": str
    }
