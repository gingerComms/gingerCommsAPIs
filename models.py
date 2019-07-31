from db import Model, Edge


class User(Model):
    """ Represents a base User account which contains all of the details
        about the User. Mainly used for Authentication
    """
    LABEL = "user"
    fields = {
        "fullName": str,
        "email": str
    }


class Account(Model):
    """ Represents an Account which can include an infinite number of Users
        and keeps track of all of the usage/subscriptions for team(s) under
        this account
    """
    LABEL = "account"
    fields = {
        "title": str,
    }


class Team(Model):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (projects/topics etc.) against other users under this Team
    """
    LABEL = "team"
    fields = {
        "name": str
    }


class UserHoldsAccount(Edge):
    """ Represents a connection between a User -> Account.
        A User can have two types of connections to an account;
        Primary and Secondary. A User can not be removed from a primary
        account, but he can be removed from a secondary account.
    """
    LABEL = "holds"
    fields = {
        "relationType": str  # primary | secondary
    }


class AccountOwnsTeam(Edge):
    """ Represents an ownership of a Team by an Account (Account -> Team).
        This is used to track financial stats for the teams [owned] by a
        given Account.
    """
    LABEL = "owns"
    fields = {}


class UserAssignedToTeam(Edge):
    """ Represents a user -> team connection from an Account's User to a
        Team.
        Only Users that HOLD the Account that OWNS the Team can be ASSIGNED_TO
        the Team
    """
    LABEL = "assigned_to"
    fields = {
        "role": str
    }
