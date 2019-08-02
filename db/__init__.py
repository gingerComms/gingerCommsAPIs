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


class PropertyValidationMixin:
    """ Mixin that includes a `validate_input` classmethod meant to be
        used to validate property data upon vertex/edge creation
    """
    @classmethod
    def validate_input(cls, data):
        """ Validates the provided data against the `properties` property
            on this Vertex/Edge using basic type checking.
        """
        errors = []
        messages = {
            "unrecognized_name": f"Property is not part of `{cls.properties}`.",
            "invalid_type": "Property is not of type `{}`"
        }

        for key, value in data.items():
            if key not in cls.properties:
                errors.append({
                    key: messages["unrecognized_name"]
                })
                continue
            if not isinstance(value, cls.properties[key]):
                errors.append({
                    key: messages["invalid_type"].format(
                        cls.properties[key].__name__
                    )
                })

        if errors:
            raise ValueError(errors)

        return data


class Model(PropertyValidationMixin):
    """ Base Model class that provides all methods required
        for a Vertex of this Model's label
    """
    # The LABEL of a model is equivalent to it's partition
    LABEL = None  # Needs to be overridden on all inheriting classes
    # A dictionary with the schema of {'property_name': <property_type>}
    # Ex: {'name': str}
    properties = {}

    def __init__(self, **kwargs):
        """ Initializes the model instances by setting attributes present
            in the kwargs
        """
        for field, value in kwargs.items():
            if field in self.properties or field == "id":
                setattr(self, field, value)

    @classmethod
    def vertex_to_instance(cls, vertex):
        """ Receives a gremlin client vertex response as input, and generates
            a Model instance based off of that
        """
        instance = cls()
        instance.id = vertex["id"]
        for field, value in vertex.get("properties", {}).items():
            setattr(instance, field, value[0]["value"])
        return instance

    @classmethod
    def create(cls, **data):
        """ Receives JSON as input and creates a new Vertex
            with the provided attributes
        """
        validated_data = cls.validate_input(data)

        query = f"g.addV('{cls.LABEL}')" + \
            f".property('{DATABASE_SETTINGS['partition_key']}', " + \
            f"'{cls.LABEL}')"

        for key, value in validated_data.items():
            query += f".property('{key}', '{value}')"

        created_vertex = client.submit(query).one()

        # Creating and returning the account object created from this query
        model_instance = cls.vertex_to_instance(created_vertex[0])

        return model_instance

    @classmethod
    def filter(cls, **properties):
        """ Returns all vertices matching the given properties
            NOTE: More complicated queries must be formulated manually.
        """
        query = f"g.V().hasLabel('{cls.LABEL}')"

        for key, value in properties.items():
            query += f".has('{key}', '{value}')"

        results = client.submit(query).all().result()

        # Converting each vertex to a Model instance
        instances = [cls.vertex_to_instance(i) for i in results]

        return instances

    def delete(self):
        """ Deletes this instance of the Model from the database """
        assert self.id, "Instance has not been initialized!"

        query = f"g.V().has('id', '{self.id}').drop()"
        res = client.submit(query).all().result()

        self.id = None
        return res


class Edge(PropertyValidationMixin):
    """ Represents a connection between two Vertices (Model Instances) """
    # Need to be overridden on all inheriting classes
    LABEL = ""
    OUTV_LABEL = ""
    INV_LABEL = ""

    @classmethod
    def edge_to_instance(cls, edge):
        """ Receives a Gremlin Edge response as input and generates an Edge
            Instance based off of it
        """
        instance = cls()
        instance.id = edge["id"]
        instance.outV, instance.inV = edge["outV"], edge["inV"]
        for field, value in edge.get("properties", {}).items():
            setattr(instance, field, value)

        return instance

    @classmethod
    def create(cls, **data):
        """ Receives the out/in vertice ids and creates an edge with the given
            properties between the two vertices
        """
        out_v, in_v = data.pop(cls.OUTV_LABEL), data.pop(cls.INV_LABEL)
        validated_data = cls.validate_input(data)

        query = f"g.V().has('id', '{out_v}').addE('{cls.LABEL}')" + \
            f".to(g.V().has('id', '{in_v}'))"

        for key, value in validated_data.items():
            query += f".property('{key}', '{value}')"

        edge = client.submit(query).one()[0]
        instance = cls.edge_to_instance(edge)

        return instance

    @classmethod
    def filter(cls, **properties):
        """ Returns all edges matching the given properties
            NOTE: More complicated queries must be formulated manually.
        """
        query = f"g.E().hasLabel('{cls.LABEL}')"

        for key, value in properties.items():
            query += f".has('{key}', '{value}')"

        results = client.submit(query).all().result()

        # Converting each edge to a Model instance
        instances = [cls.edge_to_instance(i) for i in results]

        return instances

    def delete(self):
        """ Drops this edge through the ID of the initialized instance """
        assert self.id, "Instance has not been initialized!"

        query = f"g.E().has('id', '{self.id}').drop()"
        res = client.submit(query).all().result()

        self.id = None
        return res
