from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
import copy


class TemplateCreationTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) Team Retrieve API
        2) Partial Team Update API
        3) Team Delete API  
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.user = User.create(**self.test_user_details)
        self.account = Account.create(title="TestAccount")
        self.team = Team.create(name="TestTeam")
        UserHoldsAccount.create(
            user=self.user.id, account=self.account.id, relationType="primary")
        UserAssignedToCoreVertex.create(user=self.user.id, team=self.team.id,
                                        role="team_admin")
        self.url = f"/team/{self.team.id}"

    def test_team_get(self):
        """ Tests the GET Detail API for teams """
        token = create_access_token(self.user)
        headers = self.generate_headers(token)

        r = self.client.get(
            self.url,
            headers=headers
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("id", r.json)

    def test_team_patch(self):
        """ Tests the partial update API for teams """
        token = create_access_token(self.user)
        headers = self.generate_headers(token)
        new_name = "New Team Name"

        data = {
            "name": new_name
        }
        r = self.client.patch(
            self.url,
            json=data,
            headers=headers
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("id", r.json)
        self.assertEqual(r.json["name"], new_name)

    def test_team_delete(self):
        """ Tests the delete method for teams """
        token = create_access_token(self.user)
        headers = self.generate_headers(token)

        r = self.client.delete(
            self.url,
            headers=headers
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual([], Team.filter(id=self.team.id))
