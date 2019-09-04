from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import copy


class TestTeamLinkedToOneAccountTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A team can only ever be owned by a single account, through the
            AccountOwnsTeam edge
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.team = Team.create(name="TestTeam")
        self.account = Account.create(title="TestAccount")
        self.user = User.create(**{
            "username": "TestU",
            "email": "TestE@g.com",
            "password": "TestPass",
            "fullName": "Test"
        })
        UserHoldsAccount.create(
            user=self.user.id, account=self.account.id, relationType="primary")

        super().setUp()

    def test_team_only_owned_by_one_account(self):
        """ Asserts that a team can't be owned by multiple accounts at the same
            time
        """
        first_owner = AccountOwnsTeam.create(
            account=self.account.id, team=self.team.id)

        with self.assertRaises(CustomValidationFailedException) as _:
            AccountOwnsTeam.create(
                account=self.account.id, team=self.team.id)
