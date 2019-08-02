from . import Vertex, Edge, client


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


class UserAssignedToTeam(Edge):
    """ Represents a user -> team connection from an Account's User to a
        Team.
        Only Users that HOLD the Account that OWNS the Team can be ASSIGNED_TO
        the Team
    """
    LABEL = "assigned_to"
    OUTV_LABEL = "user"
    INV_LABEL = "team"
    properties = {
        "role": str
    }
