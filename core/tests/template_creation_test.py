from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import copy


class TemplateCreationTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A Template can only be created for a Team by an Admin of said team
        2) A Template must be owned by only one team at a time  
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.user = User.create(**self.test_user_details)
        self.account = Account.create(title="TestAccount")
        UserHoldsAccount.create(
            user=self.user.id, account=self.account.id, relationType="primary")
        self.team = Team.create(name="TestTeam")
        self.url = f"/team/{self.team.id}/templates"

    def test_template_can_only_be_created_by_team_admin(self):
        """ Asserts that only the team admin should be able to create a
            template for a team
        """
        token = create_access_token(self.user)
        data = {
            "name": "TestTemplate",
            "canHaveChildren": True
        }

        # Failure: Unauthorized request
        r = self.client.post(
            self.url,
            json=data
        )
        self.assertEqual(r.status_code, 401)

        # Failure: User isn't team admin
        r = self.client.post(
            self.url,
            json=data,
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 403)

        # Success: Authorized by team admin
        UserAssignedToCoreVertex.create(
            team=self.team.id, user=self.user.id, role="team_lead")
        r = self.client.post(
            self.url,
            json=data,
            headers=self.generate_headers(token)
        )

    def test_templates_can_only_be_owned_by_one_team(self):
        """ Asserts that their can only be one team owning a template at
            any given time
        """
        team_2 = Team.create(name="Test Team 2")

        # Creating an owned edge to the first team
        template = Template.create(name="TestTemplate", canHaveChildren=True)
        TeamOwnsTemplate.create(team=self.team.id, template=template.id)

        # This should raise an exception, since it's already owned by another
        # team
        with self.assertRaises(CustomValidationFailedException) as _:
            TeamOwnsTemplate.create(team=team_2.id, template=template.id)
