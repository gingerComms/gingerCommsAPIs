from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import copy


class CoreVertexOwnershipCreationTest(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A coreVertex can only be owned by a single coreVertex/team
            at a time
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.user = User.create(**self.test_user_details)
        self.team = Team.create(name="testTeam")
        self.second_team = Team.create(name="testTeam2")
        self.first_cv = CoreVertex.create(
            title="testCV1", templateData="{}")
        self.first_cv_ownership = CoreVertexOwnership.create(
            team=self.team.id, coreVertex=self.first_cv.id)

    def test_core_vertex_owned_by_single_parent(self):
        """ Asserts that a core vertex can not be owned by multiple parents
            at a time
        """
        test_cv = CoreVertex.create(title="testCV2", templateData="{}")
        first_ownership = CoreVertexOwnership.create(
            team=self.team.id, coreVertex=test_cv.id)

        # Failure: testing that another ownership edge can't be made with
        # a coreVertex
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexOwnership.create(
                outv_id=self.first_cv.id, inv_id=test_cv.id,
                outv_label="coreVertex", inv_label="coreVertex"
            )

        # Failure: testing that another ownership edge can't be made with a
        # team
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexOwnership.create(
                team=self.second_team.id, coreVertex=test_cv.id
            )

        # Success: creating edge with cv works after destroying first edge
        first_ownership.delete()
        second_ownership = CoreVertexOwnership.create(
            outv_id=self.first_cv.id, inv_id=test_cv.id,
            outv_label="coreVertex", inv_label="coreVertex"
        )
        self.assertTrue(bool(second_ownership))
