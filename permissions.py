"""
Contains all of the permission decorators required by the flask
endpoints
"""

import flask
from flask_jwt_extended import get_jwt_identity
from flask import Response
import functools
from db.models import *


def any_team_role_required(view):
    """ Returns the view if the user has at least one role (one
        UserAssignedToTeam edge, role doesn't matter). Otherwise,
        returns a 403 response
    """
    @functools.wraps(view)
    def wrapper(team_id, *args, **kwargs):
        """ Checks the user roles through the vertex/edge methods """
        current_user = get_jwt_identity()
        if not current_user:
            flask.abort(Response({"error": "User not authenticated"}, 403,
                                 mimetype="application/json"))

        user_role = UserAssignedToTeam.get_user_assigned_role(
            team_id, current_user_id)
        if user_role is None:
            flask.abort(Response({"error": "User doesn't have any" +
                                 " permissions for this Team"}, 403,
                                 mimetype="application/json"))

        return view(team_id, *args, **kwargs)

    return wrapper
