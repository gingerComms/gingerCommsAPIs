from . import Vertex, Edge, client


class UserHoldsAccount(Edge):
    """ Represents a connection between a User -> Account.
        A User can have two types of connections to an account;
        Primary and Secondary. A User can not be removed from a primary
        account, but he can be removed from a secondary account.
    """
    LABEL = "holds"
    OUTV_LABEL = "user"
    INV_LABEL = "account"
    properties = {
        "relationType": str  # primary | secondary
    }


class AccountOwnsTeam(Edge):
    """ Represents an ownership of a Team by an Account (Account -> Team).
        This is used to track financial stats for the teams [owned] by a
        given Account.
    """
    LABEL = "owns"
    OUTV_LABEL = "account"
    INV_LABEL = "team"
    properties = {}

    @classmethod
    def get_teams(cls, account_id):
        """ Returns all teams owned by this account id """
        query = f"g.V().hasLabel('{Account.LABEL}')" + \
            f".has('id', '{account_id}').out('{cls.LABEL}')"
        results = client.submit(query).all().result()

        return [Team.vertex_to_instance(i) for i in results]


class UserAssignedToCoreVertex(Edge):
    """ Represents a user -> team|project|topic connection from an Account's
        User to a Team, Project or a Topic.
    """
    LABEL = "assigned_to"
    OUTV_LABEL = "user"
    INV_LABEL = "team"  # This should be overridden during init
    properties = {
        "role": str  # admin | lead | member
    }

    @classmethod
    def get_user_assigned_role(cls, core_vertex_id, user_id):
        """ Returns the role (UserAssignedToCoreVertex instance) assigned
            to the user for the given core-vertex
        """
        query = f"g.V().hasLabel('{cls.INV_LABEL}')" + \
            f".has('id', '{core_vertex_id}').inE('{cls.LABEL}').as('e')" + \
            f".outV().has('id', '{user_id}').select('e')"
        result = client.submit(query).all().result()

        if result:
            result = result[0]
            edge = UserAssignedToCoreVertex.edge_to_instance(result)
            return edge
        return None


class Account(Vertex):
    """ Represents an Account which can include an infinite number of Users
        and keeps track of all of the usage/subscriptions for team(s) under
        this account
    """
    LABEL = "account"
    properties = {
        "title": str,
    }


class User(Vertex):
    """ Represents a base User account which contains all of the details
        about the User. Mainly used for Authentication
    """
    LABEL = "user"
    properties = {
        "fullName": str,
        "email": str,
        "username": str,
        "password": str  # This should be a string hashed using bcrypt
    }

    def get_held_accounts(self):
        """ Returns all accounts "held by" (edge) this user """
        user_accounts_q = f"g.V().hasLabel('{self.LABEL}')" + \
                           f".has('id', '{self.id}').out('holds')" + \
                           f".hasLabel('{Account.LABEL}')"
        user_accounts = client.submit(user_accounts_q).all().result()
        user_accounts = [i["id"] for i in user_accounts]

        return user_accounts


class Team(Vertex):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (projects/topics etc.) against other users under this Team
    """
    LABEL = "team"
    properties = {
        "name": str
    }

    def get_owner(self):
        """ Returns the Account instance that owns this Team;
            indentified through the `AccountOwnsTeam` Edge
        """
        query = f"g.V().hasLabel('{self.LABEL}').has('id', '{self.id}')" + \
            f".in('{AccountOwnsTeam.LABEL}')"

        owner = client.submit(query).all().result()
        return Account.vertex_to_instance(owner[0])


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
