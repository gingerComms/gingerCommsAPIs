from marshmallow import Schema, fields


class UserRegistrationSchema(Schema):
    """ Schema for the /registration POST endpoint's input """
    fullName = fields.Str(required=True)
    email = fields.Str(required=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True)