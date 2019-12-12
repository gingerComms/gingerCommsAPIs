from db.engine import Vertex, Edge, client
from settings import DATABASE_SETTINGS
from db.exceptions import (
    CustomValidationFailedException,
    ObjectCanNotBeDeletedException
)
import auth
import re
import datetime


class TeamOwnsTemplate(Edge):
    """ Represents an Ownership Relationship (One to Many) between a
        Team to a Template.
        All children and sub-children of a team can "use" (Edge) a Template
        owned by the Team
    """
    LABEL = "owns"
    OUTV_LABEL = "team"
    INV_LABEL = "template"
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides validation to confirm that:
            1) A template is only ever owned by one team at a time
        """
        existing_edge_q = f"g.V().has('{cls.INV_LABEL}', 'id', '{inv_id}')" + \
            f".inE('owns')"
        existing_edge = client.submit(existing_edge_q).all().result()
        if existing_edge:
            raise CustomValidationFailedException(
                "Template can only be owned by a single template at a time!")

        return data

    @classmethod
    def all_team_templates(cls, team_id):
        """ Return all templates under the given team """
        query = f"g.V().has('{Team.LABEL}', 'id', '{team_id}')" + \
            f".out('{cls.LABEL}')"
        results = client.submit(query).all().result()

        return [Template.vertex_to_instance(i) for i in results]

    @classmethod
    def get_template(cls, vertex_type, vertex_id, template_id):
        """ Returns the template owned by the given:
                "Team" if the vertex_type is a `team`, or
                "CoreVertex's Root Level Team" if the vertex_type is a
                    `coreVertex`
        """
        base_template_query = f".out('{TeamOwnsTemplate.LABEL}')" + \
            f".has('id', '{template_id}')"

        if vertex_type == "team":
            # If this node is the team (root), we can just check if it has an
            # outgoing edge to this template
            query = f"g.V().has('{Team.LABEL}', 'id', '{vertex_id}')" + \
                base_template_query
        else:
            # Otherwise, we have to find the Team (Root) for this CoreVertex,
            # and then check if that team has the template
            query = f"g.V().has('{CoreVertex.LABEL}', 'id', '{vertex_id}')" + \
                f".repeat(__.in('{CoreVertexOwnership.LABEL}'))" + \
                f".until(__.hasLabel('{Team.LABEL}'))" + \
                base_template_query

        template = client.submit(query).all().result()
        if not template:
            return None
        return Template.vertex_to_instance(template[0])


class CoreVertexInheritsFromTemplate(Edge):
    """ Represents a "inheritsFrom" Relationship between a CoreVertex
        and a Template (owned (Edge) by the CoreVertice's Root Team)
    """
    LABEL = "inheritsFrom"
    OUTV_LABEL = "coreVertex"
    INV_LABEL = "template"
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides custom validation to confirm that:
            1) A Core Vertex only inherits from one template at a time and
            2) Core Vertex only inherits froom a template owned by the vertex's
                team [TODO]
        """
        # Verification for [1]
        existing_template_query = \
            f"g.V().has('{cls.OUTV_LABEL}', 'id', '{outv_id}')" + \
            f".out('{cls.LABEL}')"
        existing_template = client.submit(
            existing_template_query).all().result()
        if existing_template:
            raise CustomValidationFailedException(
                "A CoreVertex can only inherit from a single Template "
                "at a time")

        # Verification for [2]
        team_template_query = \
            f"g.V().has('{CoreVertex.LABEL}', 'id', '{outv_id}')" + \
            f".until(hasLabel('{Team.LABEL}'))" + \
            f".repeat(__.in('{CoreVertexOwnership.LABEL}')).emit()" + \
            f".out('{TeamOwnsTemplate.LABEL}')" + \
            f".has('{Template.LABEL}', 'id', '{inv_id}')"
        template_exists = client.submit(
            team_template_query).all().result()
        if not template_exists:
            raise CustomValidationFailedException(
                "The provided template either doesn't exist, or is not owned"
                "by the same team as the CoreVertex")

        return data

    @classmethod
    def get_all_template_inheritors(cls, template_id):
        """ Returns all vertices that inherit from this template id """
        query = f"g.V().has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".in('{cls.LABEL}')"

        res = client.submit(query).all().result()

        return [CoreVertex.vertex_to_instance(i) for i in res]


class UserFavoriteNode(Edge):
    """ A User -> Team/CoreVertex edge used for favoriting nodes """
    LABEL = "favoriteNode"
    OUTV_LABEL = "user"
    INV_LABEL = "team"  # can be replaced with coreVertex on init
    properties = {}

    @classmethod
    def get_favorite_nodes(cls, user_id, parent_id=None):
        """ Returns all of the favorite nodes for the given user that
            he has access to 
        """
        if parent_id:
            query = f"g.V().has('{CoreVertex.LABEL}', 'id', '{parent_id}')" + \
                f".emit()" + \
                f".until(out('{CoreVertexOwnership.LABEL}').count().is(0))" + \
                f".repeat(out('{CoreVertexOwnership.LABEL}'))"
        else:
            query = f"g.V().hasLabel('{CoreVertex.LABEL}')"
        query += f".as('cv').in('{cls.LABEL}').has('id', '{user_id}')" + \
            f".select('cv')"

        result = client.submit(query).all().result()

        nodes = []
        for node in result:
            if node["label"] == "coreVertex":
                nodes.append(CoreVertex.vertex_to_instance(node))
            else:
                nodes.append(Team.vertex_to_instance(node))

        return nodes

    @staticmethod
    def get_inbox_nodes(user_id):
        """ Returns a list of coreVertices that the user has favorited
            along with the last-message and template details
        """
        query = f"g.V().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".out('{UserFavoriteNode.LABEL}')" + \
            f".hasLabel('{CoreVertex.LABEL}').as('cv')" + \
            f".out('{NodeHasMessage.LABEL}').select('cv').dedup()" + \
            f".project('node', 'template'," + \
            f"'lastMessage', 'parent', 'lastSeenMessageTime')" + \
            f".by()" + \
            f".by(outE('{CoreVertexInheritsFromTemplate.LABEL}').inV())" + \
            f".by(outE('{NodeHasMessage.LABEL}').inV().order()" + \
            f".by('sent_at', decr).limit(1).fold())" + \
            f".by(until(__.hasLabel('{Team.LABEL}'))" + \
            f".repeat(__.inE('{CoreVertexOwnership.LABEL}').outV()).fold())" + \
            f".by(inE('{UserLastCheckedMessage.LABEL}').as('e')" + \
            f".outV().has('id', '{user_id}').select('e').values('time').fold())"

        result = client.submit(query).all().result()

        nodes = []
        for node in result:
            node_vertex = node["node"]
            # Converting to the node instance based on the label
            if node_vertex["label"] == CoreVertex.LABEL:
                node_vertex = CoreVertex.vertex_to_instance(node_vertex)
            else:
                node_vertex = Team.vertex_to_instance(node_vertex)
            # Adding the template and last message to the node
            node_vertex.template = Template.vertex_to_instance(
                node["template"])
            node_vertex.last_message = Message.vertex_to_instance(
                node["lastMessage"][0]) if node["lastMessage"] else None
            node_vertex.parentId = node["parent"][0]["id"] if \
                node["parent"] else None
            node_vertex.last_seen_time = node["lastSeenMessageTime"][0] if \
                node["lastSeenMessageTime"] else None

            nodes.append(node_vertex)
        return nodes


class Team(Vertex):
    """ Represents a Team that is "created-by" a single account
        (replaceable), and holds all of the permissions for all sub-nodes
        (coreVertices) against other users under this Team
    """
    LABEL = "team"
    properties = {
        "name": str
    }

    def get_user_permissions(self, user_id):
        """ Returns the roles assigned to the given user for this
            Team
        """
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".inE('{auth.UserAssignedToCoreVertex.LABEL}').as('e')" + \
            f".outV().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".select('e')"
        result = client.submit(query).all().result()

        return auth.UserAssignedToCoreVertex.edge_to_instance(result[0]).role \
            if result else None

    @classmethod
    def get_team_details(cls, team_id):
        """ Returns a Team object containing all of the fields required
            for the team-details endpoint(s) including:
                name, id, templates
            NOTE: This will raise an exception if the ID doesn't exist
        """
        query = f"g.V().as('team').has('{cls.LABEL}', 'id', '{team_id}')" + \
            f".fold().project('team', 'templates').by(unfold())" + \
            f".by(unfold().out('{TeamOwnsTemplate.LABEL}')" + \
            f".hasLabel('{Template.LABEL}').fold())"
        result = client.submit(query).next()[0]

        team = Team.vertex_to_instance(result["team"])
        team.templates = [
            Template.vertex_to_instance(i) for i in result["templates"]]

        return team

    @classmethod
    def get_teams_with_detail(cls, account_id, user_id):
        """ Returns all teams owned by the given account id with its
            own properties as well as the following details:
                - templatesCount,
                - member (array)
                - topicsCount
            -- Returns only the teams the user has access to
            -- SERIALIZED
        """ 
        query = f"g.V().hasLabel('{Team.LABEL}').as('team')" + \
            f".inE('{auth.AccountOwnsTeam.LABEL}').outV()" + \
            f".has('id', '{account_id}').out('{auth.AccountOwnsTeam.LABEL}')" + \
            f".inE('{auth.UserAssignedToCoreVertex.LABEL}').outV()" + \
            f".as('member')" + \
            f".out('{auth.UserAssignedToCoreVertex.LABEL}')" + \
            f".project('templatesCount', 'name', 'id', 'member', 'topicsCount')" + \
            f".by(outE('{TeamOwnsTemplate.LABEL}').inV()" + \
            f".hasLabel('{Template.LABEL}').count())" + \
            f".by(values('name'))" + \
            f".by(values('id'))" + \
            f".by(select('member'))" + \
            f".by(outE('{TeamOwnsTemplate.LABEL}').inV()" + \
            f".hasLabel('{Template.LABEL}')" + \
            f".inE('{CoreVertexInheritsFromTemplate.LABEL}').count())"
        result = client.submit(query).all().result()

        teams = {}
        for team in result:
            if team["id"] not in teams:
                teams[team["id"]] = {
                    "id": team["id"],
                    "name": team["name"],
                    "templatesCount": team["templatesCount"],
                    "topicsCount": team["topicsCount"],
                    "members": []
                }
            member = {
                "id": team["member"]["id"],
                "email": team["member"]["properties"]["email"][0]["value"],
                "avatarLink": ""  # [TODO]
            }
            if member not in teams[team["id"]]["members"]:
                teams[team["id"]]["members"].append(member)

        # Filtering to only teams that this user is a member of
        teams = list(teams.values())
        teams = [team for team in teams if user_id in [member["id"]
                 for member in team["members"]]]

        return teams


class CoreVertex(Vertex):
    """ Represents a CoreVertex instance that is based off of (inherits from)
        a template, and is under a tree with a "Team" as the Root
    """
    LABEL = "coreVertex"
    properties = {
        "title": str,
        "templateData": str,
        "content": str  # Text Field that contains formatted text
    }

    @classmethod
    def bulk_update_template_data(cls, nodes):
        """ Bulk updates the template data property for each
            node in the array - format for nodes must be:
                { nodeId: templateDataString }
        """
        query = f"g.V().hasLabel('{cls.LABEL}').choose(id())"
        for node in nodes:
            query += f".option('{node['id']}', " + \
                f"property('templateData', '{node['templateData']}'))"

        result = client.submit(query).all().result()

        return result

    def get_user_permissions(self, user_id):
        """ Returns all roles assigned to the given user for this CoreVertex
            as a dictionary of
            {direct_role: <edge>, indirect_roles: [edges...]}
        """
        # This will return all of the permissions the user has for all of the
        # vertices in this vertex's path to the root
        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}')" + \
            f".until(__.hasLabel('{Team.LABEL}'))" + \
            f".repeat(__.in('{CoreVertexOwnership.LABEL}')).path()" + \
            f".unfold().inE('{auth.UserAssignedToCoreVertex.LABEL}')" + \
            f".as('e').outV().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".select('e')"
        results = client.submit(query).all().result()

        roles = {
            "indirect_roles": [],
            "direct_role": None
        }

        for edge in results:
            if edge["inV"] == self.id:
                roles["direct_role"] = auth.UserAssignedToCoreVertex \
                    .edge_to_instance(edge).role
            else:
                roles["indirect_roles"].append(
                    auth.UserAssignedToCoreVertex.edge_to_instance(edge).role)

        return roles

    @classmethod
    def get_core_vertex_with_details(cls, vertex_id, user_id):
        """ Returns the core vertex with the following details:
            'template'
            'templateProperties'
            'path' -> breadcrumbs
            'isFavorite' -> Whether the user has this node in favorites
            with it's properties in another `template` attribute
            NOTE: Raises an exception if the vertex id isn't valid
        """
        query = f"g.V().has('{cls.LABEL}', 'id', '{vertex_id}')" + \
            f".fold().project('cv', 'template', 'templateProperties', " + \
            f"'path', 'isFavorite')" + \
            f".by(unfold())" + \
            f".by(unfold().outE('{CoreVertexInheritsFromTemplate.LABEL}')" + \
            f".inV().fold())" + \
            f".by(unfold().outE('{CoreVertexInheritsFromTemplate.LABEL}')" + \
            f".inV().outE('{TemplateHasProperty.LABEL}')" + \
            f".inV().fold())" + \
            f".by(unfold().until(__.hasLabel('team'))" + \
            f".repeat(__.in('{CoreVertexOwnership.LABEL}')).path())" + \
            f".by(unfold().inE('{UserFavoriteNode.LABEL}').outV()" + \
            f".has('id', '{user_id}').count())"

        result = client.submit(query).all().result()[0]

        core_vertex = cls.vertex_to_instance(result["cv"])
        core_vertex.template = Template.vertex_to_instance(
            result["template"][0])
        core_vertex.template.properties = [
            Template.vertex_to_instance(i) for i
            in result["templateProperties"]]
        
        # Adding the path - the first is the object itself, the last is the team
        path = result["path"]["objects"]
        core_vertex.path = []
        core_vertex.path += [CoreVertex.vertex_to_instance(i) for i in path[2:-1]]
        core_vertex.path += [Team.vertex_to_instance(path[-1])]
        core_vertex.path = reversed(core_vertex.path)
        core_vertex.isFavorite = result["isFavorite"] > 0

        return core_vertex


class TemplateProperty(Vertex):
    """ Represents an input "field" added by a user in a template """
    LABEL = "templateProperty"
    properties = {
        "name": str,
        "fieldType": str,
        # Contains certain options (list etc.) for the property; JSON str
        "propertyOptions": str,
        "index": int
    }

    @classmethod
    def update_properties_index(cls, property_ids):
        """ Receives a list of property IDs, and updates all of their
            index fields with their index in the given list
        """
        query = f"g.V().hasLabel('{cls.LABEL}').choose(id())"
        for index, prop_id in enumerate(property_ids):
            query += f".option('{prop_id}', property('index', {index}))"

        result = client.submit(query).all().result()

        return [cls.vertex_to_instance(i) for i in result]


class Message(Vertex):
    """ Represents a message sent against a node by a user """
    LABEL = "message"
    properties = {
        "text": str,
        "sent_at": str
    }

    @staticmethod
    def list_messages(node_id, start=0, end=10,
                      date_filter="gt", filter_date=None):
        """ Returns all messages sent against the given node since the
            given `since` datetime object
            NOTE: Serialized
        """
        query = f"g.V().has('id', '{node_id}')" + \
            f".out('{NodeHasMessage.LABEL}').order().by('sent_at')"

        if date_filter and filter_date:
            query += f".has('sent_at', {date_filter}('{filter_date.isoformat()}'))"

        query += f".project('id', 'text', 'sent_at', 'author')" + \
            f".by(values('id'))" + \
            f".by(values('text'))" +\
            f".by(values('sent_at'))" + \
            f".by(inE('{UserSentMessage.LABEL}').outV())"

        result = client.submit(query).all().result()
        if result:
            result = result[start:end]
            messages = []

            for item in result:
                msg = Message(
                    id=item["id"],
                    text=item["text"],
                    sent_at=item["sent_at"]
                )
                msg.author = auth.User.vertex_to_instance(item["author"])
                messages.append(msg)
            return messages
        return result


class NodeHasMessage(Edge):
    """ Represents an edge between a vertex a node and a message;
        node could be either a team/coreVertex
    """
    LABEL = "hasMessage"
    OUTV_LABEL = "team"  # Can be changed to coreVertex
    INV_LABEL = Message.LABEL
    properties = {}


class UserSentMessage(Edge):
    """ Represents an edge between a user and a message; turning the user
        into an author of the message
    """
    LABEL = "sentMessage"
    OUTV_LABEL = "user"
    INV_LABEL = Message.LABEL
    properties = {}


class UserLastCheckedMessage(Edge):
    """ Represents a continuously updated edge that shows when the user
        last read a messaeg against a node
    """
    LABEL = "lastCheckedMessages"
    OUTV_LABEL = "user"
    INV_LABEL = "team"  # This could be a coreVertex as well
    properties = {
        "time": str  # This must be an iso8601 formatted datetime object
    }

    @staticmethod
    def get_last_checked_time(user_id, node_id):
        """ Returns the time that this user last checked messages """
        query = f"g.V().has('{auth.User.LABEL}', 'id', '{user_id}')" + \
            f".outE('{UserLastCheckedMessage.LABEL}').as('e')" + \
            f".inV().has('id', '{node_id}').select('e').order()" + \
            f".by('time', decr)"
        result = client.submit(query).all().result()
        if result:
            last_read = UserLastCheckedMessage.edge_to_instance(result[0])
            return last_read
        return None


class Template(Vertex):
    """ Represents a template that has a user-defined set of custom "fields"
        that act as "templateProperties" on a CoreVertex that
        have, the root as a Team
    """
    LABEL = "template"
    properties = {
        "name": str,
        "canHaveChildren": bool,
        "pillForegroundColor": str,
        "pillBackgroundColor": str
    }

    @classmethod
    def update(cls, validated_data={}, vertex_id=None):
        """ Updates the template through the base `update` method, as well
            as added functionality for adding (DROPPING + RECREATING) the
            properties
        """
        template_properties = validated_data.pop("properties", [])

        template = super().update(validated_data=validated_data, vertex_id=vertex_id)

        # Dropping all template properties and recreating them
        if template_properties:
            drop_query = f"g.V().has('{cls.LABEL}', 'id', '{vertex_id}')" + \
                f".out('{TemplateHasProperty.LABEL}').drop()"
            client.submit(drop_query)

            # Recreating the provided template_properties
            create_query = "g.V()" + \
                f".has('{Template.LABEL}', 'id', '{template.id}').as('t')"
            for prop in template_properties:
                # Vertex Create + partition key query
                create_query += f".addV('{TemplateProperty.LABEL}')" + \
                    f".property('{DATABASE_SETTINGS['partition_key']}', " + \
                    f"'{TemplateProperty.LABEL}')"
                # A property call for each field
                for field, field_type in TemplateProperty.properties.items():
                    create_query += f".property('{field}', '{prop[field]}')"
                # The edge linking the template to the property
                create_query += f".addE('{TemplateHasProperty.LABEL}')" + \
                    ".from('t')"
            # Selecting all created properties at the end of the query
            create_query += f".outV().out('{TemplateHasProperty.LABEL}')"

            res = client.submit(create_query).all().result()
            template.properties = [
                TemplateProperty.vertex_to_instance(i) for i in res]

        return template

    @classmethod
    def get_template_with_properties(cls, template_id, parent_team_id=None):
        """ Returns the template and the template properties belonging to it
            in a single query
        """
        query = "g.V()"
        # Prepending a team query if the team id arg is provided
        if parent_team_id:
            query += f".has('{Team.LABEL}', 'id', " + \
                f"'{parent_team_id}').out('{TeamOwnsTemplate.LABEL}')"
        query += f".has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".fold().project('template', 'properties').by(unfold())" + \
            f".by(unfold().out('{TemplateHasProperty.LABEL}').fold())"

        try:
            # This raises a 597 error if there's nothing found
            res = client.submit(query).all().result()
        except:
            return None

        template = Template.vertex_to_instance(res[0]["template"])
        template.properties = [
            TemplateProperty.vertex_to_instance(i) for i
            in res[0]["properties"]]

        return template

    @classmethod
    def get_templates_with_details(cls, team_id):
        """ Returns the all Template instance owned by the given team
            with the required details;
                - id, name, topicsCount
            -- SERIALIZED
        """
        query = f"g.V().has('{Team.LABEL}', 'id', '{team_id}')" + \
            f".out('{TeamOwnsTemplate.LABEL}').hasLabel('{Template.LABEL}')" + \
            f".project('id', 'name', 'topicsCount', 'properties')" + \
            f".by(values('id')).by(values('name'))" + \
            f".by(inE('{CoreVertexInheritsFromTemplate.LABEL}').outV()" + \
            f".hasLabel('{CoreVertex.LABEL}').count())" + \
            f".by(outE('{TemplateHasProperty.LABEL}').inV().fold())"
        result = client.submit(query).all().result()

        templates = []
        for template in result:
            properties = [TemplateProperty.vertex_to_instance(i)
                          for i in template["properties"]]
            template["properties"] = []
            for prop in properties:
                template["properties"].append({
                    "id": prop.id,
                    "name": prop.name,
                    "fieldType": prop.fieldType,
                    "propertyOptions": prop.propertyOptions,
                    "index": prop.index
                })
            templates.append(template)

        return templates


class TemplateHasProperty(Edge):
    """ Represents an outward edge from a Template to a TemplateProperty,
        identifying that a Template has a particular Property
    """
    LABEL = "hasProperty"
    OUTV_LABEL = Template.LABEL
    INV_LABEL = TemplateProperty.LABEL
    properties = {}

    @classmethod
    def get_template_properties(cls, template_id):
        """ Returns all TemplateProperties belonging to the given template """
        query = f"g.V().has('{Template.LABEL}', 'id', '{template_id}')" + \
            f".out('{cls.LABEL}')"

        res = client.submit(query).all().result()

        return [TemplateProperty.vertex_to_instance(i) for i in res]


class CoreVertexOwnership(Edge):
    """ Represents a Parental Relationship between CoreVertices;
        Teams can own CoreVertices and CoreVertices can own other CoreVertices
        if the Template they inherit from has the "hasChildren" bool set to
        True
    """
    LABEL = "owns"
    # This can be overridden during create (team | coreVertex)
    OUTV_LABEL = "team"
    INV_LABEL = CoreVertex.LABEL
    properties = {}

    @classmethod
    def custom_validation(cls, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ Provides validation to confirm that
            1) A coreVertex is only ever owned by one team/coreVertex at a time
            2) A coreVertex can only be owned by a coreVertex whose Template
                 has the canHaveChildren property set to True
        """
        existing_edge_q = f"g.V().has('{inv_label}', 'id', '{inv_id}')" + \
            f".inE('owns')"
        existing_edge = client.submit(existing_edge_q).all().result()
        if existing_edge:
            raise CustomValidationFailedException(
                "CoreVertex can only be owned by a single parent at a time!")

        # Checking for the template's canHaveChildren property if the
        # parent is a coreVertex
        if outv_label == "coreVertex":
            parent_template_query = \
                f"g.V().has('{outv_label}', 'id', '{outv_id}')" + \
                f".out('{CoreVertexInheritsFromTemplate.LABEL}')"
            parent_template = Template.vertex_to_instance(
                client.submit(parent_template_query).all().result()[0])
            if parent_template.canHaveChildren != "True":
                raise CustomValidationFailedException(
                    "CoreVertex can only be owned by a CoreVertex that has"
                    " it's template's canHaveChildren property set to `true`!")

        return data

    @classmethod
    def get_children(cls, parent_id, parent_type, template_id=None):
        """ Returns all DIRECT children coreVertices under the given
            parent
        """
        query = f"g.V().has('{parent_type}', 'id', '{parent_id}')" + \
            f".out('{cls.LABEL}').hasLabel('{CoreVertex.LABEL}')"

        if template_id:
            query += f".as('cv')" + \
                f".out('{CoreVertexInheritsFromTemplate.LABEL}')" + \
                f".has('id', '{template_id}').select('cv')"

        result = client.submit(query).all().result()

        return [CoreVertex.vertex_to_instance(i) for i in result]

    @staticmethod
    def get_children_tree(parent_id, user_id):
        """ Returns the children of the given parent node in a tree view
            list format as [ {'name': '...', 'children': [...]} ] with their
            direct sub-children
                - Also returns an isFavorite value for each child
        """
        query = f"g.V().has('id', '{parent_id}').out('owns')" + \
            f".hasLabel('{CoreVertex.LABEL}').as('children')" + \
            f".select('children').by(project('topChild', 'template', 'sub_children')" + \
            f".by()" + \
            f".by(outE('{CoreVertexInheritsFromTemplate.LABEL}').inV())" + \
            f".by(outE('{CoreVertexOwnership.LABEL}').inV()" + \
            f".hasLabel('{CoreVertex.LABEL}').as('subchild')" + \
            f".outE('{CoreVertexInheritsFromTemplate.LABEL}').inV()" + \
            f".as('subchildTemplate').select('subchild')" + \
            f".map(outE('{CoreVertexOwnership.LABEL}').inV()" + \
            f".hasLabel('{CoreVertex.LABEL}').count()).as('childCount')" + \
            f".select('subchild', 'subchildTemplate', 'childCount').fold()))"

        tree = []
        favorite_nodes = UserFavoriteNode.get_favorite_nodes(
            user_id, parent_id=parent_id)
        favorite_nodes = [i.id for i in favorite_nodes]

        # Raises an exception if there are NO direct children
        try:
            result = client.submit(query).all().result()
        except:
            return tree

        for child_data in result:
            child = CoreVertex.vertex_to_instance(child_data["topChild"])
            child.template = CoreVertex.vertex_to_instance(
                child_data["template"])
            child.isFavorite = child.id in favorite_nodes
            sub_children = []

            for sub_child in child_data["sub_children"]:
                cv = CoreVertex.vertex_to_instance(sub_child["subchild"])
                cv.isFavorite = cv.id in favorite_nodes
                cv.template = Template.vertex_to_instance(
                    sub_child["subchildTemplate"])
                if sub_child["childCount"] > 0:
                    print(sub_child["childCount"], cv.title)
                    cv.children = []
                sub_children.append(cv)
            if sub_children:
                child.children = sub_children

            tree.append(child)

        return tree

    @classmethod
    def get_root(cls, core_vertex_id):
        """ Returns the team vertex at the base of this core-vertex
            ownership tree
            [UNTESTED]
        """
        query = \
            f"g.V().has('{CoreVertex.LABEL}', 'id', '{core_vertex_id}')" + \
            f".until(hasLabel('{Team.LABEL}')).repeat(out('{cls.LABEL}'))"

        team = client.submit(query).all().result()[0]
        return Team.vertex_to_instance(team)
