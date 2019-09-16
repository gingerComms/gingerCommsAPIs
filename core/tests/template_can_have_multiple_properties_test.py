from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from core.models import *
from db.engine import client
import copy


class TemplateCanHaveMultiplePropertiesTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) A template can have more than one property attached to it
    """
    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        self.user = User.create(**self.test_user_details)
        self.template = Template.create(name="testTemplate", canHaveChildren=True)

    def test_template_can_have_multiple_properties(self):
        """ Asserts that a template can parent multiple properties through
            edges
        """
        property_1 = TemplateProperty.create(name="prop1", fieldType="string")
        property_2 = TemplateProperty.create(name="prop2", fieldType="string")

        edge_1 = TemplateHasProperty.create(
            template=self.template.id, templateProperty=property_1.id)
        edge_2 = TemplateHasProperty.create(
            template=self.template.id, templateProperty=property_2.id)

        self.assertTrue(edge_1)
        self.assertTrue(edge_2) 