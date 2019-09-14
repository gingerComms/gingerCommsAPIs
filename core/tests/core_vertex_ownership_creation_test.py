from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import copy
import time


class CoreVertexOwnershipCreationTest(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A coreVertex can only be owned by a single coreVertex/team
            at a time
        2) A coreVertex can only be owned by a coreVertex which has it's
            template's canHaveChildren property set to True
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

        time.sleep(0.5)
        self.first_cv_template = Template.create(
            name="Temp", canHaveChildren=True)
        TeamOwnsTemplate.create(team=self.team.id,
                                template=self.first_cv_template.id)
        CoreVertexInheritsFromTemplate.create(
            coreVertex=self.first_cv.id, template=self.first_cv_template.id)

        # Failure: testing that another ownership edge can't be made with
        # a coreVertex
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexOwnership.create(
                outv_id=self.first_cv.id, inv_id=test_cv.id,
                outv_label="coreVertex", inv_label="coreVertex"
            )

        time.sleep(0.5)

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

    def test_core_vertex_can_only_be_owned_by_canhavechildren_true(self):
        """ Asserts that a core vertex can only be owned by another coreVertex
            if the parent's template has it's canHaveChildren property set to
            True
        """
        test_cv = CoreVertex.create(title="testCV2", templateData="{}")

        self.first_cv_template = Template.create(
            name="Temp", canHaveChildren=False)
        TeamOwnsTemplate.create(team=self.team.id,
                                template=self.first_cv_template.id)
        CoreVertexInheritsFromTemplate.create(
            coreVertex=self.first_cv.id, template=self.first_cv_template.id)

        # Failure test - canHaveChildren set to False
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexOwnership.create(
                outv_id=self.first_cv.id, inv_id=test_cv.id,
                outv_label="coreVertex", inv_label="coreVertex"
            )

        # Success test - canHaveChildren set to True
        self.first_cv_template.update(
            {"canHaveChildren": True}, self.first_cv_template.id)
        CoreVertexOwnership.create(
            outv_id=self.first_cv.id, inv_id=test_cv.id,
            outv_label="coreVertex", inv_label="coreVertex"
        )

