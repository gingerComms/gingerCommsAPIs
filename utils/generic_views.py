from .mixins import *
from flask.views import MethodView


class RetrieveAPIView(RetrieveVertexMixin, MethodView):
    """ MethodView endpoint that defines a `get` method
        which uses the RetrieveVertexMixin to return the desired
        vertex to the user
    """
    def get(self, *args, **kwargs):
        return self.retrieve()


class UpdateAPIView(UpdateVertexMixin, MethodView):
    """ MethodView endpoint that defines the `put` and `patch` methods
        which perform update and partial updates on a given vertex
        respectfully through the UpdateVertexMixin
    """
    def put(self, *args, **kwargs):
        return self.update()

    def patch(self, *args, **kwargs):
        return self.update(partial=True)


class RetrieveUpdateAPIView(RetrieveVertexMixin, UpdateVertexMixin,
                            MethodView):
    """ MethodView endpoint that combines both the Retrieve and Update
        APIViews to provide the Detail GET and Update PATCH/PUT Methods
    """
    def get(self, *args, **kwargs):
        return self.retrieve()

    def put(self, *args, **kwargs):
        return self.update()

    def patch(self, *args, **kwargs):
        return self.update(partial=True)