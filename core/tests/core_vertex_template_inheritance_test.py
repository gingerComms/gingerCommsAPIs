from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
from db.exceptions import CustomValidationFailedException
import time


class CoreVertexTemplateInheritanceTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A Core Vertex can only inherit from a single template, and;
        2) A Core Vertex can only inherit from a template owned by the
            vertex tree's root Team
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
        self.core_vertex = CoreVertex.create(
            title="Test CV", templateData="{}")
        self.template = Template.create(
            name="Test Template", canHaveChildren=True)

        self.core_v_to_team_ownership = CoreVertexOwnership.create(
            team=self.team.id, coreVertex=self.core_vertex.id)

    def test_core_vertex_inherits_from_single_template(self):
        """ Asserts that a coreVertex can only inherit from a single template
            at any given time
        """
        # Creating the team -> template edge so that we can try linking the
        # coreVertex to the template
        TeamOwnsTemplate.create(team=self.team.id, template=self.template.id)

        # Failure case; coreVertex already linked to another template
        template_2 = Template.create(
            name="TestTemplate2", canHaveChildren=True)
        TeamOwnsTemplate.create(team=self.team.id, template=template_2.id)
        core_vertex_inheritance = CoreVertexInheritsFromTemplate.create(
            coreVertex=self.core_vertex.id, template=template_2.id)
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexInheritsFromTemplate.create(
                coreVertex=self.core_vertex.id, template=self.template.id)

        # Success case
        core_vertex_inheritance.delete()
        core_vertex_inheritance = CoreVertexInheritsFromTemplate.create(
            coreVertex=self.core_vertex.id, template=self.template.id)
        self.assertTrue(bool(core_vertex_inheritance))

    def test_core_vertex_template_owned_by_team(self):
        """ Asserts that a coreVertex's inherited template is owned by the team
            in it's root
        """
        # Failure case; template not owned by core vertex's team
        with self.assertRaises(CustomValidationFailedException) as _:
            CoreVertexInheritsFromTemplate.create(
                coreVertex=self.core_vertex.id, template=self.template.id)

        # Success case
        TeamOwnsTemplate.create(team=self.team.id, template=self.template.id)
        core_vertex_inheritance = CoreVertexInheritsFromTemplate.create(
            coreVertex=self.core_vertex.id, template=self.template.id)
        self.assertTrue(bool(core_vertex_inheritance))
