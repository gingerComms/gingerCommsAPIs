"""
Contains all of the permission decorators required by the flask
endpoints
"""

import flask
from flask_jwt_extended import get_jwt_identity
from flask import make_response
import functools
from core.models import *
from auth.models import *
from flask import jsonify


def has_core_vertex_parental_permissions(view):
    """ Returns the view if the authenticated user has access to the
        given `parent_node`'s in some form (through a parent/indirectly)
        Also injects the parent_vertex instance into view through a named arg
    """
    @functools.wraps(view)
    def wrapper(self, *args, **kwargs):
        return view(*args, **kwargs)

    return wrapper


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
        user_accounts = user.get_held_accounts()
        if not account.id in user_accounts:
            return flask.abort(make_response(
                jsonify({"error": "Account is not held by the user."}), 403))

        return view(*args, account=account, user=user,
                    account_id=account_id, **kwargs)

    return wrapper


def any_core_vertex_role_required(view):
    """ Returns the view if the user has at least one role (one
        UserAssignedToCoreVertex edge, role doesn't matter). Otherwise,
        returns a 403 response
        Also injects a "core_vertex" and "current_user_role" parameter
        into the view
    """
    CORE_VERTEX_MAPS = {
        "team": Team,
        "project": Project
    }

    @functools.wraps(view)
    def wrapper(*args, vertex_type=None, vertex_id=None, **kwargs):
        """ Checks the user roles through the vertex/edge methods """
        current_user = get_jwt_identity()
        vertex_model = CORE_VERTEX_MAPS[vertex_type]

        core_vertex = vertex_model.filter(id=vertex_id)
        if not core_vertex:
            return flask.abort(make_response(
                jsonify({"error": "Input Team does not exist."}), 404))
        core_vertex = core_vertex[0]

        user_role = UserAssignedToCoreVertex(inv_label=vertex_type) \
            .get_user_assigned_role(vertex_id, current_user)
        if user_role is None:
            flask.abort(make_response(
                        jsonify({"error": "User lacks team role"}),
                        403))

        return view(*args, vertex_id=vertex_id, core_vertex=core_vertex,
                    vertex_type=vertex_type, current_user_role=user_role,
                    **kwargs)

    return wrapper
