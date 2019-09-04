from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
import copy


class TeamCreationTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A team can only be created under an account by a user holding
            that account
        2) The account holder of a team owned by the account is the admin
            of the team by default (UserAssignedToCoreVertex)
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.user = User.create(**self.test_user_details)
        self.account = Account.create(title="TestAccount")
        UserHoldsAccount.create(
            user=self.user.id, account=self.account.id, relationType="primary")

    def test_user_can_only_be_created_by_account_holder(self):
        """ Asserts that a team can only be created by a person holding
            the account that will own the team
        """
        unheld_account = Account.create(title="Account2")
        token = create_access_token(self.user)

        # Failure test; unheld account
        r = self.client.post(
            f"/account/{unheld_account.id}/teams",
            json={
                "name": "TestTeam"
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 403)

        # Success test; account held by user
        r = self.client.post(
            f"/account/{self.account.id}/teams",
            json={
                "name": "TestTeam"
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 201)

    def test_account_holder_is_team_admin_on_creation(self):
        """ Asserts that the account holder making the team creation request
            if the Team admin by default
        """
        token = create_access_token(self.user)

        r = self.client.post(
            f"/account/{self.account.id}/teams",
            json={
                "name": "TestTeam"
            },
            headers=self.generate_headers(token)
        )

        permission_edge = UserAssignedToCoreVertex.filter(
            outv_id=self.user.id, inv_id=r.json["id"],
            role="admin")
        self.assertTrue(bool(permission_edge))
        self.assertEqual(permission_edge[0].outV, self.user.id)
