import functools
import flask
from flask import make_response, jsonify
from auth.models import User, Account
from flask_jwt_extended import get_jwt_identity


def account_held_by_user(view):
    """ Returns the view if the account id passed into the view is held in
        some form by the user (primary/secondary)
        Also injects the account and user instances into the view
    """
    @functools.wraps(view)
    def wrapper(*args, account_id=None, **kwargs):
        """ Checks whether the account is held by the user through the User
            model Methods
        """
        user_id = get_jwt_identity()
        user = User.filter(id=user_id)[0]

        account = Account.filter(id=account_id)
        if not account:
            return flask.abort(make_response(
                jsonify({"error": "Account does not exist!"}), 404))
        account = account[0]

        # Confirming that the account is a user account
        user_accounts = user.get_held_accounts(user.id)
        if not account.id in user_accounts:
            return flask.abort(make_response(
                jsonify({"error": "Account is not held by the user."}), 403))

        return view(*args, account=account, user=user,
                    account_id=account_id, **kwargs)

    return wrapper
