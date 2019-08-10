from marshmallow import Schema, fields


class TeamSchema(Schema):
    """ Schema for the basic Team Vertex and it's endpoints """
    name = fields.Str(required=True)


class CoreVertexListSchema(Schema):
    """ Schema used for CoreVertex List endpoints; contains only the
        minimal details
    """
    id = fields.Str(required=False)
    title = fields.Str(required=True)


class TemplateSchema(Schema):
    """ Schema for the Template including all of it's properties [TODO] """
    id = fields.Str(required=True)
    name = fields.Str(required=True)
    canHaveChildren = fields.Bool(required=True)
