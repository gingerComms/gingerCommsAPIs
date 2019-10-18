from .general_utils import jsonify_response
from flask import request
import json


class RetrieveVertexMixin:
    """ Mixin that implements a "retrieve" method that uses other class
        methods/attributes to fetch a Vertex instance from the database
        and return it's serialized form through a Response
    """
    def retrieve(self, *args, **kwargs):
        """ Uses the `serializer_class` to serialize the object returned by
            the `get_object` method, and returns the serialized data to the
            user
        """
        if not getattr(self, "serializer_class", None):
            raise ValueError("The `serializer_class` must be provided!")

        schema = self.serializer_class()
        instance = self.get_object()
        if not instance:
            return jsonify_response({
                "error": "Instance not found"
            }, 404)
        serialized_data = schema.dumps(instance).data

        return jsonify_response(json.loads(serialized_data), 200)


class UpdateVertexMixin:
    """ Mixin that implements an "update" method that can be used in
        MethodViews to update vertices; (pass in partial=True for partial
        updates) Uses the Vertex Class's "update" method to update the
        properties
    """
    def update(self, partial=False):
        """ Uses the `vertex_class` property to update the vertex identified
            by the `get_vertex_id()` method with the data present in the
            request
            The request data is validated by the `serializer_class` attribute
        """
        if not self.serializer_class:
            raise ValueError("The `serializer_class` attribute must be set")

        if not self.vertex_class:
            raise ValueError("The `vertex_class` attribute must be set")

        schema = self.serializer_class(partial=partial)
        validation = schema.loads(request.data)
        if validation.errors:
            return jsonify_response({"errors": validation.errors}, 400)
        validated_data = validation.data

        vertex = self.vertex_class.update(vertex_id=self.get_vertex_id(),
                                          validated_data=validated_data)
        if not vertex:
            return jsonify_response({"error": "Vertex not found!"}, 404)

        return jsonify_response(json.loads(schema.dumps(vertex).data), 200)


class DeleteVertexMixin:
    """ Mixin that implements a "delete" method that can be used in MethodViews
        for deleting vertices.
        Note that deleting a vertex through this mixin will automatically
        delete all of it's edges to prevent having any stray edges
    """
    def delete(self):
        """ Uses the `get_object()` method to find the target vertex, and
            delete the vertex along with all of it's in and out edges
        """
        if not self.serializer_class:
            raise ValueError("The `serializer_class` attribute must be set")

        if not self.vertex_class:
            raise ValueError("The `vertex_class` attribute must be set")

        instance = self.get_object()
        if not instance:
            return jsonify_response({
                "error": "Instance not found"
            }, 404)
        instance.delete()

        return jsonify_response({
            "status": "Vertex Deleted"
        }, 200)
