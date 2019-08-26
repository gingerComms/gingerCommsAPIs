from flask_testing import TestCase
from api import app
from db.engine import client
import time
from settings import DATABASE_SETTINGS


class FlaskTestCase(TestCase):
    """ Contains the basic flask app-creation method and fixtures that are
        shared among all of the unit tests
    """
    def create_app(self):
        """ Inititalizes and returns a Flask App instance """
        app.config["TESTING"] = True
        app.set_verbose = True
        return app

    def setUp(self):
        """ Test fixtures run on test initialization """
        self.partition_key = DATABASE_SETTINGS['partition_key']

    def tearDown(self):
        """ Clears the database after each test """
        # This is to keep the request rate under control for CosmosDB Emulator
        time.sleep(1)
        client.submit("g.V().drop()").all().result()

    def generate_headers(self, token):
        """ Returns the authentication headers given the token """
        return {"Authorization": "Bearer %s" % token}
