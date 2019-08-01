from flask import Flask, request, jsonify
import json
from db.models import *
from serializers import *


app = Flask(__name__)


def jsonify_response(data, status_code=200):
    """ Returns a response object with the given data of mimetype
        application/json with the given status code
    """
    return app.response_class(response=data,
                              status=status_code,
                              mimetype="application/json")


@app.route("/", methods=["GET"])
def index():
    """ Base index page for server configuration testing """
    return jsonify({
        "message": "Success!"
    })


@app.route("/register", methods=["POST"])
def register():
    """ A POST Endpoint used for creation of new Users (and their primary
        accounts, indirectly)
    """
    schema = UserRegistrationSchema()

    data = schema.loads(request.data)
    if data.errors:
        return jsonify(data.errors), 400

    # Creating the User and it's primary account
    user = User.create(**data.data)
    account = Account.create(title=f"Primary Account for {user.fullName}")
    edge = UserHoldsAccount.create(user=user.id, account=account.id,
                                   relationType="primary")

    return jsonify_response(schema.dumps(user).data, 201)


@app.route("/account/<account_id>/team", methods=["POST"])
def create_team(account_id):
    """ A POST endpoint used for the creation of new secondary Accounts
        linked to the currently authenticated users

        TODO: Add part that verifies that this account is somehow connected
            to the authenticated user
    """
    account = Account.filter(id=account_id)
    if not account:
        return jsonify_response({"error": "Account does not exist!"}, 404)
    account = account[0]

    schema = TeamSchema()
    data = schema.loads(request.data)
    if data.errors:
        return jsonify_response(data.errors, 400)

    team = Team.create(**data.data)
    edge = AccountOwnsTeam.create(account=account.id, team=team.id)

    return jsonify_response(schema.dumps(team).data, 201)


if __name__ == "__main__":
    app.run(debug=True)
