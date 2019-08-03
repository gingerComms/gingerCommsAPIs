from flask_testing import TestCase
import unittest
from api import app, bcrypt
from db.models import *
from db import client
import copy
import time


class VpmoTestCase(TestCase):
    """ Contains all of the tests for the Vpmo API Endpoints """
    user_creds = {
        "fullName": "Test User",
        "email": "test@gmail.com",
        "username": "testuser",
        "password": "testpass"
    }

    def create_app(self):
        """ Inititalizes and returns a Flask App instance """
        app.config["TESTING"] = True
        return app

    def tearDown(self):
        """ Clears the database after each test """
        # This is to keep the request rate under control for CosmosDB Emulator
        time.sleep(2)
        client.submit("g.V().drop()").all().result()

    def test_index(self):
        """ Tests that the index page returns successfully """
        r = self.client.get("/")

        self.assertEqual(r.status_code, 200)

    def test_user_registration(self):
        """ Tests the user registration POST endpoint """
        url = "/register"
        r = self.client.post(url, json=self.user_creds)
        self.assertEqual(r.status_code, 201)

    def test_user_login(self):
        """ Tests the authentication endpoint for users """
        user_creds = copy.copy(self.user_creds)
        user_creds["password"] = bcrypt.generate_password_hash(
            self.user_creds["password"]).decode("utf-8")
        user = User.create(**user_creds)

        url = "/login"
        r = self.client.post(url, json={
            "username": self.user_creds["username"],
            "password": self.user_creds["password"]
        })
        self.assertEqual(r.status_code, 200)

        return r.json

    def test_team_creation(self):
        """ Tests the team creation POST endpoint """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]

        account = Account.create(title="Test Account for Team")
        url = f"/account/{account.id}/team"

        r = self.client.post(
            url,
            json={"name": "Test Team"},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 403)

        edge = UserHoldsAccount.create(user=user, account=account.id)

        r = self.client.post(
            url,
            json={"name": "Test Team"},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201)

    def test_account_creation(self):
        """ Tests the Account creation POST endpoint """
        url = "/create_account"
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]

        r = self.client.post(
            url,
            json={"title": "Test Account."},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201)

if __name__ == "__main__":
    unittest.main()
