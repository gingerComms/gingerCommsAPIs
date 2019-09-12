from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import copy


class CoreVertexTeamPermissionsTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A CoreVertex can be read by team-admins and team leads
        2) A CoreVertex can be updated by team-admins
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.team = Team.create(name="Test Team")
        self.core_vertex = CoreVertex.create(title="TestCV", templateData="{}")
        self.cv_owned_by_team = CoreVertexOwnership.create(
            team=self.team.id, coreVertex=self.core_vertex.id)
        self.user = User.create(**self.test_user_details)
        self.url = f"/coreVertex/{self.core_vertex.id}"

    def test_admin_or_lead_can_read_core_vertex(self):
        """ Asserts that a user with a team-lead/admin role can read a
            CV through the detail and list endpoints
        """
        token = create_access_token(self.user)

        # Failure case - unauthorized
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 401)

        # Failure case - authorized but no role edge
        r = self.client.get(
            self.url,
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 403)

        # Success case - authorized with team-admin to team
        admin_edge = UserAssignedToCoreVertex.create(
            team=self.team.id, user=self.user.id, role="team_admin")
        r = self.client.get(
            self.url,
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 200)
