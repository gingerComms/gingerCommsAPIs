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

            NOTE: This currently ddoesn't check for REQUIRED PROPERTIES [TODO]
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


class Vertex(PropertyValidationMixin):
    """ Base Vertex class that provides all methods required
        for a Vertex of this Vertex's label
    """
    # The LABEL of a Vertex is equivalent to it's partition
    LABEL = None  # Needs to be overridden on all inheriting classes
    # A dictionary with the schema of {'property_name': <property_type>}
    # Ex: {'name': str}
    properties = {}

    def __init__(self, **kwargs):
        """ Initializes the Vertex instances by setting attributes present
            in the kwargs
        """
        for field, value in kwargs.items():
            if field in self.properties or field == "id":
                setattr(self, field, value)

    @classmethod
    def vertex_to_instance(cls, vertex):
        """ Receives a gremlin client vertex response as input, and generates
            a Vertex instance based off of that
        """
        instance = cls()
        instance.id = vertex["id"]
        for field, value in vertex.get("properties", {}).items():
            setattr(instance, field, value[0]["value"])
        return instance

    @classmethod
    def custom_validation(self, data):
        """ A Validation method meant to be overridden by specific vertex
             Models and all Vertex-specific validation should go in here
        """
        return data

    @classmethod
    def create(cls, **data):
        """ Receives JSON as input and creates a new Vertex
            with the provided attributes
        """
        validated_data = cls.validate_input(data)
        validated_data = cls.custom_validation(data)

        query = f"g.addV('{cls.LABEL}')" + \
            f".property('{DATABASE_SETTINGS['partition_key']}', " + \
            f"'{cls.LABEL}')"

        for key, value in validated_data.items():
            query += f".property('{key}', '{value}')"

        created_vertex = client.submit(query).one()

        # Creating and returning the account object created from this query
        vertex_instance = cls.vertex_to_instance(created_vertex[0])

        return vertex_instance

    @classmethod
    def filter(cls, wildcard_properties=[], limit=None, **properties):
        """ Returns all vertices matching the given properties
            NOTE: More complicated queries must be formulated manually.
            Wildcard properties can be sent in as TextP.startingWith('val'),
            and they must be part of the `wildcard_properties` array
        """
        query = f"g.V().hasLabel('{cls.LABEL}')"

        for key, value in properties.items():
            if key in wildcard_properties:
                query += f".has('{key}', {value})"
            else:
                query += f".has('{key}', '{value}')"

        if limit:
            query += f".limit({limit})"

        results = client.submit(query).all().result()

        # Converting each vertex to a Vertex instance
        instances = [cls.vertex_to_instance(i) for i in results]

        return instances

    def delete(self):
        """ Deletes this instance of the Vertex from the database """
        assert self.id, "Instance has not been initialized!"

        query = f"g.V().has('{self.LABEL}', 'id', '{self.id}').drop()"
        res = client.submit(query).all().result()

        self.id = None
        return res

    @classmethod
    def update(cls, validated_data={}, vertex_id=None):
        """ Updates the properties of the initialized vertex (this instance)
            in the database with the provided data
            The vertex can be identified either with the `vertex_id` parameter
            or through the initialized class's `id` property

            NOTE: It is assumed that this data has been validated already!
            NOTE 2: This method DOES NOT update the instance in place!
        """
        assert "id" not in validated_data, "Can not update Vertex ID!"
        assert vertex_id, "No vertex identifier provided!"

        query = f"g.V().has('{cls.LABEL}', 'id', '{vertex_id}')"
        for key, value in validated_data.items():
            query += f".property('{key}', '{value}')"

        res = client.submit(query).all().result()

        # An empty list means that the query ran unsuccessfully
        # (i.e. nonexistent vertex)
        if not res:
            return None

        return cls.vertex_to_instance(res[0])


class Edge(PropertyValidationMixin):
    """ Represents a connection between two Vertices (Vertex Instances) """
    # Need to be overridden on all inheriting classes
    LABEL = ""
    OUTV_LABEL = ""
    INV_LABEL = ""

    def __init__(self, *args, outv_label=None, inv_label=None, **kwargs):
        """ Modifiess the inv label attribute for this instance
            The main purpose of this is to be able to use the same edge
            methods along multiple kinds of "CoreVertices" (Team|CoreVertex)
        """
        self.OUTV_LABEL = outv_label or self.OUTV_LABEL
        self.INV_LABEL = inv_label or self.INV_LABEL

    @classmethod
    def edge_to_instance(cls, edge):
        """ Receives a Gremlin Edge response as input and generates an Edge
            Instance based off of it
        """
        instance = cls(inv_label=cls.INV_LABEL)
        instance.id = edge["id"]
        instance.outV, instance.inV = edge.get("outV"), edge.get("inV")
        for field, value in edge.get("properties", {}).items():
            setattr(instance, field, value)

        return instance

    @classmethod
    def custom_validation(self, data, outv_id=None, inv_id=None,
                          outv_label=None, inv_label=None):
        """ A Validation method meant to be overridden by specific edge Models
            and all Edge-specific validation should go in here
        """
        return data

    @classmethod
    def generate_create_query(cls, outv_label=None, inv_label=None,
                              outv_id=None, inv_id=None):
        """ Returns a formatted Gremlin Query string that can be used
            as a base for an edge Create query (before adding properties)
        """
        return f"g.V().has('{outv_label}', 'id', '{outv_id}')" + \
            f".addE('{cls.LABEL}')" + \
            f".to(g.V().has('{inv_label}', 'id', '{inv_id}'))"

    @classmethod
    def create(cls,
               outv_id=None, inv_id=None,
               outv_label=None, inv_label=None,
               **data):
        """ Receives the out/in vertice ids and creates an edge with the given
            properties between the two vertices
        """
        # To allow support of the same label relationships
        # :: provide outv_id and inv_id parameters if INV_LABEL == OUTV_LABEL
        out_v = outv_id or data.pop(cls.OUTV_LABEL)
        in_v = inv_id or data.pop(cls.INV_LABEL)
        OUTV_LABEL = outv_label or cls.OUTV_LABEL
        INV_LABEL = inv_label or cls.INV_LABEL

        assert isinstance(out_v, str)
        assert isinstance(in_v, str)

        validated_data = cls.validate_input(data)
        validated_data = cls.custom_validation(
            validated_data, outv_id=out_v, inv_id=in_v,
            outv_label=OUTV_LABEL, inv_label=INV_LABEL)

        query = cls.generate_create_query(
            outv_label=OUTV_LABEL, inv_label=INV_LABEL,
            outv_id=out_v, inv_id=in_v
        )

        for key, value in validated_data.items():
            query += f".property('{key}', '{value}')"

        edge = client.submit(query).all().result()[0]
        instance = cls.edge_to_instance(edge)

        return instance

    @classmethod
    def filter(cls, outv_id=None, inv_id=None,
               outv_label=None, inv_label=None, **properties):
        """ Returns all edges matching the given properties between the
            given out and in vertices
        """
        OUTV_LABEL = outv_label or cls.OUTV_LABEL
        INV_LABEL = inv_label or cls.INV_LABEL

        # Filtering by the out and in vertices if provided, otherwise just
        # the properties
        if outv_id and inv_id:
            query = f"g.V().has('{OUTV_LABEL}', 'id', '{outv_id}')" + \
                f".outE('{cls.LABEL}').as('e')" + \
                f".inV().has('{INV_LABEL}', 'id', '{inv_id}')" + \
                f".select('e')"
        else:
            query = f"g.E().hasLabel('{cls.LABEL}')"

        for key, value in properties.items():
            query += f".has('{key}', '{value}')"

        results = client.submit(query).all().result()

        # Converting each edge to an `Edge` class instance
        instances = [cls.edge_to_instance(i) for i in results]

        return instances

    def delete(self):
        """ Drops this edge through the ID of the initialized instance
            TODO: This currently deletes just the vertex and leaves hanging vertices
                if there are any edges.
                Raise an error if vertex as any outgoing edges
        """
        assert self.id, "Instance has not been initialized!"

        query = f"g.E().has('id', '{self.id}').drop()"
        res = client.submit(query).all().result()

        self.id = None
        return res
