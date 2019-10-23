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
import inspect


def core_vertex_permission_decorator_factory(overwrite_vertex_type=None,
                                             direct_allowed_roles=[],
                                             indirect_allowed_roles=[]):
    def has_core_vertex_permissions(view):
        """ Returns the view if the authenticated user has one of the required
            roles for the requested core-vertex (directly/through a
            parent)
                - Also injects the `vertex` instance identified by the id
                into the view
        """
        # `vertex_type` to cls map
        classes = {
            "team": Team,
            "coreVertex": CoreVertex
        }

        @functools.wraps(view)
        def wrapper(*args, vertex_type=None, vertex_id=None, **kwargs):
            """ Uses the provided instance methods to confirm that the user
                has access to the node
            """
            current_user = get_jwt_identity()

            if overwrite_vertex_type is not None:
                vertex_type = overwrite_vertex_type

            vertex = classes[vertex_type].filter(id=vertex_id)
            vertex = vertex[0] if vertex else None

            # If this a team vertex, we only need to care about direct roles
            if vertex_type == "team":
                matched_role = classes[vertex_type].filter(id=vertex_id)[0].get_user_permissions(current_user) in direct_allowed_roles
                print(classes[vertex_type].filter(id=vertex_id)[0].get_user_permissions(current_user),
                      current_user, vertex_id)
                if not matched_role:
                    return flask.abort(make_response(
                        jsonify({"error": "User lacks required role."}), 403))
            # Otherwise, we need to check both direct and indirect roles for
            # coreVertices
            elif vertex_type == "coreVertex":
                vertex_roles = vertex.get_user_permissions(current_user)
                direct_vertex_role = vertex_roles["direct_role"]
                indirect_vertex_roles = vertex_roles["indirect_roles"]

                indirect_match = [
                    i for i in indirect_vertex_roles if i in
                    indirect_allowed_roles]
                direct_match = direct_vertex_role in direct_allowed_roles

                if not direct_match and not indirect_match:
                    return flask.abort(make_response(
                        jsonify({"error": "User lacks required role."}), 403))

            return view(*args, vertex=vertex, vertex_type=vertex_type,
                        vertex_id=vertex_id, **kwargs)

        return wrapper

    return has_core_vertex_permissions


def any_core_vertex_role_required(view):
    """ Returns the view if the user has at least one role (one
        UserAssignedToCoreVertex edge, role doesn't matter). Otherwise,
        returns a 403 response
        Also injects a "core_vertex" and "current_user_role" parameter
        into the view
    """
    CORE_VERTEX_MAPS = {
        "team": Team,
        "coreVertex": CoreVertex
    }

    @functools.wraps(view)
    def wrapper(*args, vertex_type=None, vertex_id=None, **kwargs):
        """ Checks the user roles through the vertex/edge methods """
        current_user = get_jwt_identity()
        vertex_type = vertex_type if vertex_type == "team" else "coreVertex"
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
