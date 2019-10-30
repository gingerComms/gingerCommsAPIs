from marshmallow import Schema, fields, validates, ValidationError
from .models import TemplateHasProperty
import json


class TemplatePropertySchema(Schema):
    """ Schema for TemplateProperties """
    id = fields.Str(dumps_only=True)
    name = fields.Str(required=True)
    fieldType = fields.Str(required=True)
    propertyOptions = fields.Str(required=True)
    index = fields.Integer(required=False)


class TemplateDetailSchema(Schema):
    """ Schema for the Template including all of it's properties [TODO] """
    id = fields.Str(dumps_only=True)
    name = fields.Str(required=True)
    canHaveChildren = fields.Bool(dumps_only=True)
    properties = fields.Method("get_template_properties", dumps_only=True)
    pillForegroundColor = fields.Str(required=True)
    pillBackgroundColor = fields.Str(required=True)

    def get_template_properties(self, obj):
        """ Uses the template methods to get a serialized list of
            properties
        """
        if obj.properties and isinstance(obj.properties, list):
            properties = obj.properties
        else:
            properties = TemplateHasProperty.get_template_properties(obj.id)

        data = TemplatePropertySchema(many=True).dumps(properties)
        return json.loads(data.data)

    @validates("properties")
    def validate_properties(self, value):
        """ Validator for the properties array """
        schema = TemplatePropertySchema(many=True)
        errors = schema.validate(value)

        if errors:
            raise ValidationError(errors)


class TemplateListSchema(Schema):
    """ Schema used for the templates list endpoinnts """
    id = fields.Str(dumps_only=True)
    name = fields.Str(required=True)
    canHaveChildren = fields.Bool(required=True)
    pillForegroundColor = fields.Str(required=True)
    pillBackgroundColor = fields.Str(required=True)


class TeamSchema(Schema):
    """ Schema for the basic Team Vertex and it's endpoints """
    name = fields.Str(required=True)
    id = fields.Str(dumps_only=True)


class TeamsListSchema(Schema):
    """ Schema used for the TeamsList endpoint """
    name = fields.Str(required=True)
    id = fields.Str(dumps_only=True)


class TeamsDetailSchema(Schema):
    """ Schema used for the TeamsDetail endpoints """
    name = fields.Str(required=True)
    id = fields.Str(dumps_only=True)
    templates = fields.Nested(TemplateListSchema, many=True, dumps_only=True)


class CoreVertexListSchema(Schema):
    """ Schema used for CoreVertex List endpoints; contains only the
        minimal details
    """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
    content = fields.Str(required=True)


class CoreVertexDetailSchema(Schema):
    """ Schema used for CoreVertex Detail endpoints; contains all of the
        details, including the template details [TODO: ADD TEMPLATE DETAILS]
    """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
    template = fields.Nested(TemplateDetailSchema,
                             required=False,
                             dumps_only=True)
    content = fields.Str(required=True)


class CoreVertexTreeSchema(Schema):
    """ Schema used for CoreVertex Tree List view endpoint """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
    template = fields.Nested(TemplateListSchema,
                             required=False,
                             dumps_only=True)
    content = fields.Str(required=True)


class TreeViewListSchema(Schema):
    """ Schema used for the TreeListView for core-vertices/teams """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
    template = fields.Nested(TemplateListSchema,
                             required=False,
                             dumps_only=True)
    children = fields.Nested(CoreVertexDetailSchema,
                             many=True,
                             dumps_only=True)
