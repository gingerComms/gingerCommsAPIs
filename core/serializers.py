from marshmallow import Schema, fields, validates, ValidationError
from .models import TemplateHasProperty
import json


class TeamSchema(Schema):
    """ Schema for the basic Team Vertex and it's endpoints """
    name = fields.Str(required=True)
    id = fields.Str(dumps_only=True)


class TeamsListSchema(Schema):
    """ Schema used for the TeamsList endpoint """
    name = fields.Str(required=True)
    id = fields.Str(required=True)
    members = fields.Method("get_members")

    def get_members(self, obj):
        """ All members with access to the Team [TODO] """
        return []

    def get_stats(self, obj):
        """ Total number of coreVertices that have this team as
            the root and the total number of templates owned
            by this team
        """



class CoreVertexListSchema(Schema):
    """ Schema used for CoreVertex List endpoints; contains only the
        minimal details
    """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)


class TemplatePropertySchema(Schema):
    """ Schema for TemplateProperties """
    id = fields.Str(dumps_only=True)
    name = fields.Str(required=True)
    fieldType = fields.Str(required=True)


class TemplateSchema(Schema):
    """ Schema for the Template including all of it's properties [TODO] """
    id = fields.Str(dumps_only=True)
    name = fields.Str(required=True)
    canHaveChildren = fields.Bool(required=True)
    properties = fields.Method("get_template_properties")

    def get_template_properties(self, obj):
        """ Uses the template methods to get a serialized list of
            properties
        """
        if obj.properties:
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


class CoreVertexDetailSchema(Schema):
    """ Schema used for CoreVertex Detail endpoints; contains all of the
        details, including the template details [TODO: ADD TEMPLATE DETAILS]
    """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
