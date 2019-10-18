from marshmallow import Schema, fields
import json


class UserRegistrationSchema(Schema):
    """ Schema for the /registration POST endpoint's input """
    fullName = fields.Str(required=True)
    email = fields.Str(required=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class UserListSchema(Schema):
    """ Basic List schema including base details for the User Vertex """
    fullName = fields.Str(required=True)
    email = fields.Str(required=True)
    username = fields.Str(required=True)


class AccountDetailSchema(Schema):
    """ Detail schema for Account instances with an additional list
        of users
    """
    id = fields.Str(required=False)
    title = fields.Str(required=True)
    users = fields.Method("get_account_users")

    def get_account_users(self, obj):
        """ Returns all users holding this account as well as their
            relationship
        """
        return ["TEMPORARILY DISABLED TO PREVENT REQUEST"
                "RATE TOO LARGE ERROR!"]
        users = obj.get_users()
        data = UserListSchema(many=True).dumps(users)
        data = json.loads(data.data)
        return data


class AccountsListSchema(Schema):
    """ List schema for account instances with only the required details """
    title = fields.Str(required=True)
    id = fields.Str(required=False)
