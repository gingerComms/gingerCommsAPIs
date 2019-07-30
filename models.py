from db import Model


class Account(Model):
    """ Represents an Account which can include an infinite number of Users
        and keeps track of all of the usage/subscriptions for team(s) under
        this account
    """
    _label = "account"
    fields = {
        "accountType": str,
    }
