from flask_testing import TestCase
import unittest
from api import app, bcrypt
from auth.models import *
from core.models import *
from db.engine import client
import copy
import json
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
        url = "/auth/register"
        r = self.client.post(url, json=self.user_creds)
        self.assertEqual(r.status_code, 201)

    def test_user_login(self, username=None, password=None):
        """ Tests the authentication endpoint for users """
        if not username and not password:
            user_creds = copy.copy(self.user_creds)
            user_creds["password"] = bcrypt.generate_password_hash(
                self.user_creds["password"]).decode("utf-8")
            user = User.create(**user_creds)

        url = "/auth/login"
        r = self.client.post(url, json={
            "username": username or self.user_creds["username"],
            "password": password or self.user_creds["password"]
        })
        self.assertEqual(r.status_code, 200)

        return r.json

    def test_account_creation(self):
        """ Tests the Account creation POST endpoint """
        url = "/auth/create_account"
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]

        r = self.client.post(
            url,
            json={"title": "Test Account."},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201, r.json)

    def test_team_role_retrieve(self):
        """ Tests the Team Role retrieval endpoint """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team = Team.create(name="Test Team")
        edge = UserAssignedToCoreVertex.create(user=user, team=team.id,
                                         role="admin")

        url = f"/team/{team.id}/roles"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["role"], "admin", r.json)

        second_user = User.create(username="test", email="test",
                                  password="test", fullName="test")
        r = self.client.get(
            url+f"?user={second_user.id}",
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["role"], None, r.json)

    def test_team_role_creation(self):
        """ Tests the Team Role post endpoint (for creating/updating user
            roles)
        """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team = Team.create(name="Test Team")
        edge = UserAssignedToCoreVertex.create(user=user, team=team.id,
                                         role="admin")

        second_user_pass = "test"
        second_user_pass_hash = bcrypt.generate_password_hash(
            second_user_pass).decode("utf-8")
        second_user = User.create(username="test", email="test",
                                  password=second_user_pass_hash,
                                  fullName="test")

        url = f"/team/{team.id}/roles"

        # No roles to lead test (by admin) - success
        r = self.client.post(
            url+f"?user={second_user.id}",
            json={"role": "lead"},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["role"], "lead", r.json)

        # Lead to admin test (by lead) - fail
        logged_in = self.test_user_login(username=second_user.username,
                                         password=second_user_pass)
        user, token = logged_in["user"]["id"], logged_in["token"]
        r = self.client.post(
            url,
            json={"role": "admin"},
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 403, r.json)

    def test_teams_list_create_view(self):
        """ Tests the team creation and listing endpoint """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]

        account = Account.create(title="Test Account for Team")
        url = f"/account/{account.id}/teams"

        # Testing the creation endpoints (403 Forbidden and 200 Success)
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

        # Testing the LIST endpoint
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(json.loads(r.json)), 1)

    def test_core_vertex_creation(self):
        """ Tests the CoreVertex creation endpoint used for creating
            CoreVertices under Teams or other CoreVertices
        """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team = Team.create(name="Test Team")
        user_team_edge = UserAssignedToCoreVertex.create(user=user,
                                                         team=team.id,
                                                         role="admin")
        # Adding a template undewr the User to create the new CoreVertex off of
        template = Template.create(name="Project", canHaveChildren=True)
        team_template_edge = TeamOwnsTemplate.create(team=team.id,
                                                     template=template.id)
        url = f"/team/{team.id}/children/"

        data = {
            "title": "The Test Project",
            "template": template.id
        }
        r = self.client.post(
            url,
            json=data,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201, r.status_code)
        self.assertEqual(r.json["title"], "The Test Project", r.json)

        created_node = r.json["id"]
        url = f"coreVertex/{created_node}/children/"
        data = {
            "title": "The Test Project 2",
            "template": template.id
        }
        r = self.client.post(
            url,
            json=data,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201, r.status_code)
        self.assertEqual(r.json["title"], "The Test Project 2", r.json)

        return team.id, created_node

    def test_core_vertex_list(self):
        """ Tests the LIST endpoint that lists all coreVertices under the given
            team/coreVertex
        """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        created_team, created_node = self.test_core_vertex_creation()

        url = f"/team/{created_team}/children/"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.status_code)
        self.assertEqual(len(r.json), 1, r.json)

        url = f"/coreVertex/{created_node}/children/"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.status_code)
        self.assertEqual(len(r.json), 1)

    def test_templates_creation_view(self):
        """ Tests the create endpoint for creating new templates owned by
            a team
        """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team = Team.create(name="Test Team")
        user_team_edge = UserAssignedToCoreVertex.create(user=user,
                                                         team=team.id,
                                                         role="admin")

        data = {"name": "Template Test", "canHaveChildren": True}
        url = f"/team/{team.id}/templates/"
        r = self.client.post(
            url,
            json=data,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 201, r.json)
        self.assertEqual(r.json["name"], "Template Test", r.json)

        return team.id, r.json["id"]

    def test_templates_list_view(self):
        """ Tests the LIST view for listing all templates under a team """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        created_team, created_template = self.test_templates_creation_view()

        url = f"/team/{created_team}/templates/"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json), 1, r.json)
        self.assertEqual(r.json[0]["id"], created_template, r.json)

if __name__ == "__main__":
    unittest.main()
