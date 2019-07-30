from gremlin_python.driver import serializer
from gremlin_python.driver.client import Client
from settings import DATABASE_SETTINGS


client = Client(
    DATABASE_SETTINGS["host"],
    DATABASE_SETTINGS["traversal_source"],
    username=DATABASE_SETTINGS["username"],
    password=DATABASE_SETTINGS["password"],
    message_serializer=serializer.GraphSONSerializersV2d0()
)


class Model:
    """ Base Model class that provides all methods required
        for a Vertex of this Model's label
    """
    _label = ""
    # A dictionary with the schema of {'field_name': <field_type>}
    # Ex: {'name': str}
    fields = {}

    @property
    def label(self):
        """ Represents the label identifier for all Vertices """
        if not self._label:
            raise NotImplementedError("The _label field must be overwritten"
                                      " by all model classes.")
        return self._label

    @property
    def partition(self):
        """ CosmosDB requires a partition key value for all of instances
            in a Database; it is used to identify different kinds of
            objects. We can just use the label as a default since they
            both serve the same purpose in a different capacity.
        """
        return self.label

    @classmethod
    def validate_input(cls, data):
        """ Validates the provided data against the `fields` property
            on this Model using basic type checking.
        """
        errors = []
        messages = {
            "unrecognized_name": f"Field is not part of `{cls.fields}`.",
            "invalid_type": "Field is not of type {}"
        }

        for key, value in data:
            if key not in cls.fields:
                errors.append({
                    key: messages["unrecognized_name"]
                })
                continue
            if not isinstance(value, cls.fields[key]):
                errors.append({
                    key: messages["invalid_type"].format(cls.fields[key])
                })

        if errors:
            raise ValueError(errors)

        return data

    @classmethod
    def create(cls, data):
        """ Receives JSON as input and creates a new Vertex
            with the provided attributes
        """
        validated_data = cls.validate_input(data)

        query = f"g.addV({cls.label})" + \
            f".addProperty('{DATABASE_SETTINGS['partition_key']}', " + \
            f"{cls.partition})"

        for key, value in validated_data.items():
            query += f".addProperty('{key}', '{value}')"

        return client.submit(query).next()


class Edge:
    """ Represents a connection between two Vertices (Model Instances) """
    _label = ""

    @property
    def label(self):
        """ Represents the label identifier for all Vertices """
        if not self._label:
            raise NotImplementedError("The _label field must be overwritten"
                                      " by all model classes.")
        return self._label

    @classmethod
    def create(cls, out_v, in_v, data):
        """ Receives the out/in vertices and creates an edge with the given
            properties between the twoo vertices
        """
        # client.submit("g.V().has('name', 'Marko').addE('created').to(g.V().has('name', 'Marko2'))")
        pass
