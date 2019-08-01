from flask_testing import TestCase
import unittest
from api import app
from db.models import Account


class VpmoTestCase(TestCase):
    """ Contains all of the tests for the Vpmo API Endpoints """
    def create_app(self):
        """ Inititalizes and returns a Flask App instance """
        app.config["TESTING"] = True
        return app

    def test_index(self):
        """ Tests that the index page returns successfully """
        r = self.client.get("/")

        self.assertEqual(r.status_code, 200)

    def test_user_registration(self):
        """ Tests the user registration POST endpoint """
        url = "/register"
        r = self.client.post(url, json={
            "fullName": "Test User",
            "email": "wigeriaaeriag@gmail.com"
        })
        self.assertEqual(r.status_code, 201)

    def test_team_creation(self):
        """ Tests the team creation POST endpoint """
        account = Account.create(title="Test Account")
        url = f"/account/{account.id}/team"
        r = self.client.post(url, json={"name": "Test Team"})

        self.assertEqual(r.status_code, 201)


if __name__ == "__main__":
    unittest.main()
