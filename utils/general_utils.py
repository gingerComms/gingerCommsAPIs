from api import app
import json


def jsonify_response(response, status=200):
    """ Returns the dict response as json with the provided status code """
    return app.response_class(
        response=json.dumps(response),
        status=status, mimetype="application/json")
