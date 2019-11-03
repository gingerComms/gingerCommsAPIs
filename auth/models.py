from db.engine import Vertex, Edge, client
from db.exceptions import (
    CustomValidationFailedException,
    ObjectCanNotBeDeletedException
)
import core


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

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides custom validation before creation that verifies that
            1) The User doesn't already hold the account in some form, and;
            2) The Account targeted doesn't already have a primary holder
                while a new primary holder is going to be added upon this
                edge's creation [TODO]
        """
        user_query = f"g.V().has('{User.LABEL}', 'id', '{outv_id}')"
        existing_edge_query = user_query + \
            f".outE('{cls.LABEL}')" + \
            f".inV().has('{Account.LABEL}', 'id', '{inv_id}')"
        existing_primary_edge = client.submit(existing_edge_query) \
            .all().result()

        if existing_primary_edge:
            raise CustomValidationFailedException(
                "User already holds account!")

        return data

    def delete(self):
        """ Overwritten to provide custom validation before deleting the
            edge
        """
        if self.relationType == "primary":
            raise ObjectCanNotBeDeletedException(
                "Can not remove a User from a primary Account")

        return super().delete()


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
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides custom validation to confirm that:
            1) This team (inv) isn't already owned by another team
        """
        existing_edge = AccountOwnsTeam.filter(
            outv_id=outv_id, inv_id=inv_id)
        if existing_edge:
            raise CustomValidationFailedException(
                f"Targeted team is already owned by another account")

        return data

    @classmethod
    def get_teams(cls, account_id):
        """ Returns all teams owned by this account id """
        query = f"g.V().hasLabel('{Account.LABEL}')" + \
            f".has('id', '{account_id}').out('{cls.LABEL}')"
        results = client.submit(query).all().result()

        return [core.Team.vertex_to_instance(i) for i in results]

    @classmethod
    def get_team_owner(self, team_id):
        """ Returns the Account instance that owns the given team """
        query = f"g.V().hasLabel('{core.Team.LABEL}').has('id', '{team_id}')" + \
            f".in('{AccountOwnsTeam.LABEL}')"

        owner = client.submit(query).all().result()
        return Account.vertex_to_instance(owner[0])


class UserAssignedToCoreVertex(Edge):
    """ Represents a user -> team|coreVertex connection from an Account's
        User to a Team or CoreVertex.
    """
    LABEL = "assignedTo"
    OUTV_LABEL = "user"
    # This could be overridden during create (team | coreVertex)
    INV_LABEL = "team"
    # Could be a choice between: ["team_lead", "team_admin", "team_member"]
    # for teams, and: ["cv_lead", "cv_admin", "cv_member"] for core_vertices
    properties = {
        "role": str
    }

    @classmethod
    def get_user_assigned_role(cls, core_vertex_id, user_id, inv_label=None):
        """ Returns the role (UserAssignedToCoreVertex instance) assigned
            to the user for the given core-vertex
        """
        INV_LABEL = inv_label or cls.INV_LABEL
        query = f"g.V().hasLabel('{INV_LABEL}')" + \
            f".has('id', '{core_vertex_id}').inE('{cls.LABEL}').as('e')" + \
            f".outV().has('id', '{user_id}').select('e')"
        result = client.submit(query).all().result()

        if result:
            result = result[0]
            edge = UserAssignedToCoreVertex.edge_to_instance(result)
            return edge
        return None

    @classmethod
    def get_members(cls, vertex_type, vertex_id):
        """ Returns a list of members (id, email, avatarLink, role) that
            are assigned to the given coreVertex
                - SERIALIZED
        """
        query = f"g.V().has('{vertex_type}', 'id', '{vertex_id}')" + \
            f".inE('{cls.LABEL}').as('e')" + \
            f".outV().as('user').project('id', 'email', 'role')" + \
            f".by(select('user').values('id'))" + \
            f".by(select('user').values('email'))" + \
            f".by(select('e').values('role'))"
        result = client.submit(query).all().result()

        for i in result:
            i["avatarLink"] = None

        return result


class Account(Vertex):
    """ Represents an Account which can include an infinite number of Users
        and keeps track of all of the usage/subscriptions for team(s) under
        this account
        account id = slugify(title)@[username]
    """
    LABEL = "account"
    properties = {
        "title": str,
    }

    def get_users(self):
        """ Returns all users who "hold" this account through the
            UserHoldsAccount edge
        """
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".in('{UserHoldsAccount.LABEL}').hasLabel('{User.LABEL}')"
        r = client.submit(query).all().result()

        return [User.vertex_to_instance(i) for i in r]


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

    @classmethod
    def get_held_accounts(cls, user_id, initialize_models=False):
        """ Returns all accounts "held by" (edge) this user or the accounts
             that the user has access to at least one of the teams in

            If the `initialize_models` arg is True, the vertexes are converted
            into Account models before being returned; otherwise they're
            returned as IDs
        """
        user_accounts_q = f"g.V().has('{cls.LABEL}', 'id', '{user_id}')" + \
                           f".as('u').out('{UserHoldsAccount.LABEL}')" + \
                           f".hasLabel('{Account.LABEL}')" + \
                           f".store('accounts').select('u')" + \
                           f".out('{UserAssignedToCoreVertex.LABEL}')" + \
                           f".hasLabel('team').in('{AccountOwnsTeam.LABEL}')" + \
                           f".store('accounts').cap('accounts')" + \
                           f".unfold().dedup()"
        user_accounts = client.submit(user_accounts_q).all().result()

        if initialize_models:
            return [Account.vertex_to_instance(i) for i in user_accounts]
        else:
            return [i["id"] for i in user_accounts]
