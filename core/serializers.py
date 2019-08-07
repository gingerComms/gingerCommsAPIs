from marshmallow import Schema, fields


class TeamSchema(Schema):
    """ Schema for the basic Team Vertex and it's endpoints """
    name = fields.Str(required=True)
