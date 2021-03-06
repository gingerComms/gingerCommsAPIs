from marshmallow import Schema, fields, validates, ValidationError
from .models import *
import auth.serializers
import json


class MessageListSchema(Schema):
    """ Schema for message lists """
    id = fields.Str(dumps_only=True)
    text = fields.Str(required=True)
    sent_at = fields.Str(dumps_only=True)
    author = fields.Nested(auth.serializers.UserListSchema, dumps_only=True)


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


class GenericNodeSchema(Schema):
    """ Basic schema for nodes - used for breadcrumbs/favorite nodes """
    id = fields.Str(dumps_only=True)
    displayName = fields.Method("get_display_name", dumps_only=True)
    label = fields.Method("get_label", dumps_only=True)

    def get_label(self, obj):
        """ Returns `coreVertex` for coreVertices and `team` for Teams """
        if isinstance(obj, CoreVertex):
            return "coreVertex"
        return "team"

    def get_display_name(self, obj):
        """ Returns the title for coreVertices and name for Teams """
        if isinstance(obj, CoreVertex):
            return obj.title
        return obj.name


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
    path = fields.Nested(GenericNodeSchema, many=True, dumps_only=True)
    isFavorite = fields.Boolean(required=False, dumps_only=True)


class CoreVertexTreeSchema(Schema):
    """ Schema used for CoreVertex Tree List view endpoint """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    templateData = fields.Str(required=True)
    template = fields.Nested(TemplateListSchema,
                             required=False,
                             dumps_only=True)
    content = fields.Str(required=True)
    isFavorite = fields.Boolean(required=True)
    children = fields.List(fields.Str(required=False),
                           required=False)


class TreeViewListSchema(Schema):
    """ Schema used for the TreeListView for core-vertices/teams """
    id = fields.Str(dumps_only=True)
    title = fields.Str(required=True)
    isFavorite = fields.Boolean(required=True)
    templateData = fields.Str(required=True)
    template = fields.Nested(TemplateListSchema,
                             required=False,
                             dumps_only=True)
    children = fields.Nested(CoreVertexTreeSchema,
                             many=True,
                             dumps_only=True)


class InboxNodesSchema(Schema):
    """ Schema used for the inbox-dialog that handles both teams and
        coreVertices
    """
    id = fields.Str(dumps_only=True)
    name = fields.Method("get_display_name", dumps_only=True)
    nodeType = fields.Method("get_node_type", dumps_only=True)
    template = fields.Nested(TemplateListSchema,
                             required=False,
                             dumps_only=True)
    last_message = fields.Nested(MessageListSchema,
                                required=False,
                                dumps_only=True)
    parentId = fields.Str(dumps_only=True)
    last_seen_time = fields.Str(dumps_only=True)

    def get_node_type(self, obj):
        """ Returns `coreVertex` for coreVertices and `team` for Teams """
        if isinstance(obj, CoreVertex):
            return "coreVertex"
        return "team"

    def get_display_name(self, obj):
        """ Returns the title for coreVertices and name for Teams """
        if isinstance(obj, CoreVertex):
            return obj.title
        return obj.name
