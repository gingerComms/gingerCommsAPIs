from flask_testing import TestCase
import unittest
from api import app, bcrypt
from auth.models import *
from core.models import *
from db.engine import client
import copy
import json
import time
from core.serializers import *


class VpmoTestCase(TestCase):
    """ Contains all of the tests for the Vpmo API Endpoints """
    user_creds = {
        "fullName": "Test User",
        "email": "test@gmail.com",
        "username": "testuser",
        "password": "testpass"
    }

    user_creds2 = {
        "fullName": "Test User 2",
        "email": "test2@gmail.com",
        "username": "testuser",
        "password": "testpass"
    }



    def create_app(self):
        """ Initializes and returns a Flask App instance """
        app.config["TESTING"] = True
        app.set_verbose = True
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

    def test_user_register_with_duplicate_username(self):
        """ Test that user registration with an already existing
            username raises error
        """
        url = "/auth/register"
        first_response = self.client.post(url, json=self.user_creds)
        second_response = self.client.post(url, json=self.user_creds2)
        self.assertEqual(second_response.status_code, 400)

    @unittest.skip("pending development")
    def test_user_register_with_duplicate_email(self):
        """ Test that user registration with an already existing email
            raises error
        """

    def test_user_registration_result_in_account_creation(self):
        """
            Given:              a non-registered user
            when:               signs up
            then:               a personal account is automatically created
                                and gets associated with the user vertex
            steps:              1- non-registered user signs up
            expected result:    1- user gets registered with a unique username and password
                                2- personal account is created
                                3- User -holds-> Account
                                4- account id account@[username]
        """

        url = "/auth/register"

        r = self.client.post(url, json=self.user_creds)
        username = r.json['username']
        user = User.filter(id=username)
        self.assertIn("account@"+r.json["username"], user.get_held_accounts())

    @unittest.skip("pending development")
    def test_account_duplicate_name(self):
        """ Test that account with duplicate id cannot be created
            account id is: [account name (defined by user)]@username
            example for account id: account@user123
        """

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

    @unittest.skip("pending development")
    def test_team_linked_to_one_account(self):
        """ Test that team is linked to an account and only one account
            at a time.
            - Assert that team is owned by an account
            - Assert that team is owned only by one account
        """


    def test_team_role_retrieve(self):
        """ Tests the Team Role retrieval endpoint """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team = Team.create(name="Test Team")
        edge = UserAssignedToCoreVertex.create(
            user=user, team=team.id, role="admin")

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
        edge = UserAssignedToCoreVertex.create(
            user=user, team=team.id, role="admin")

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
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(len(r.json), 1, r.json)
        self.assertEqual(r.json[0]["id"], created_template, r.json)

    def test_core_vertex_update_view(self):
        """ Tests the PATCH/PUT endpoint for updating a coreVertex """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        created_team, created_node = self.test_core_vertex_creation()

        # PUT (full update) test for the coreVertex
        url = f"/coreVertex/{created_node}/"
        data = {
            "title": "New Name",
            "templateData": "{}"
        }
        r = self.client.put(
            url,
            json=data,
            headers={
                "Authorization": "Bearer %s" % token,
                "Content-Type": "application/json"
            }
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["title"], "New Name")
        self.assertEqual(r.json["templateData"], "{}")

        # PATCH (partial update) test for the coreVertex
        new_template_data = "{\"name\": \"Good Project\"}"
        data = {
            "templateData": new_template_data
        }
        r = self.client.patch(
            url,
            json=data,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["title"], "New Name")
        self.assertEqual(data["templateData"], new_template_data)

    def test_core_vertex_retrieve_view(self):
        """ Tests the retrieve endpoint for CoreVertices """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        created_team, created_node = self.test_core_vertex_creation()

        url = f"/coreVertex/{created_node}/"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["id"], created_node)

    def test_templates_retrieve_view(self):
        """ Tests the update template view for a Template in a given Team """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        created_team, created_template = self.test_templates_creation_view()

        # Adding properties to the template
        template_property = TemplateProperty.create(
            name="Name", fieldType="String")
        property_edge = TemplateHasProperty.create(
            template=created_template, templateProperty=template_property.id)

        url = f"/team/{created_team}/templates/{created_template}/"
        r = self.client.get(
            url,
            headers={"Authorization": "Bearer %s" % token}
        )

        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["id"], created_template, r.json)
        self.assertEqual(len(r.json.get("properties", [])), 1, r.json)

        return created_team, created_template, template_property.id

    def test_templates_update_view(self):
        """ Tests the full and partial update template views """
        logged_in = self.test_user_login()
        user, token = logged_in["user"]["id"], logged_in["token"]
        team, template, template_property = self.test_templates_retrieve_view()

        url = f"/team/{team}/templates/{template}/"

        # Full Update (PUT) Test
        r = self.client.put(
            url,
            json={
                "name": "New Template Name",
                "canHaveChildren": False,
                "properties": [
                    {
                        "name": "String Field Name",
                        "fieldType": "String"
                    },
                    {
                        "name": "String Field 2 Name",
                        "fieldType": "String"
                    }
                ]
            },
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["name"], "New Template Name", r.json)

        # Partial Update (PATCH) Test
        r = self.client.patch(
            url,
            json={
                "name": "Template Name 2"
            },
            headers={"Authorization": "Bearer %s" % token}
        )
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["name"], "Template Name 2", r.json)
        self.assertEqual(len(r.json["properties"]), 2, r.json)

    @unittest.skip("pending development")
    def test_template_owned_by_team(self):
        """ Assert a team owns template
            Assert only one team owns template
        """


    @unittest.skip("pending development")
    def test_corevertex_inherits_from_template(self):
        """
            given:              system
            when:               checking a given coreVertex
            then:               it always inherits from a Template
            steps:              1- create a CoreVertex
                                2- link the CoreVertex to a Template
                                3- link the same CoreVertex to another Template
            expected result:    1- system enforces the selection of a Template during CoreVertex creation
                                2- CoreVertex is only created with an inheritsFrom edge to a Template
                                3- system triggers an error when trying to

        """

    @unittest.skip("pending development")
    def test_corevertex_switch_to_another_template(self):
        """
            given:              user with admin access to CoreVertex
            when:               trying to switch from one template to another
            then:               coreVertex gets de-linked from the current Template
                                and gets linked to the new Template
            steps:              1- create or identify and existing a Template
                                2- create a coreVertex inheriting from the Template above
                                3- create or identify another Template
                                4- shift inheritsFrom edge to the second Template
            expected results:   1- coreVertex properties will be as of
                                    the properties in the second Template
        """

    @unittest.skip("pending development")
    def test_property_is_owned_by_template(self):
        """
            given:              system
            when:               checking a given property
            then:               there is always a hasProperty edge to one template
            expected result:    1- property (vertex) is linked to a template
                                2- edge is Labeled hasProperty

        """

    @unittest.skip("pending development")
    def test_corevertex_is_owned_by_team(self):
        """ Assert that one and only one team owns corevertex """


    @unittest.skip("pending development")
    def test_template_creation_by_non_admin(self):
        """
            Step:               1- non-admin user attempts to create a template
            Expected result:    1- error response 'only team admin can create template'
        """

    @unittest.skip("pending development")
    def test_template_creation_by_admin(self):
        """
            Given:              a team admin
            when:               attempting to create a template
            then:               I should be able to create a template linked to team
            steps:              1- team admin user attempts to create a template
            expected result:    1- template is created
                                2- Team -owns-> Template
                                3- User -created-> Template
        """


if __name__ == "__main__":
    unittest.main()
