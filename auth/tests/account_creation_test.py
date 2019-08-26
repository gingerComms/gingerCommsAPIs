from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from db.engine import client


class AccountCreationTestCase(FlaskTestCase):
    """ Contains the tests related to the secondary account creation
        endpoint

        # TODO:
            Other potential tests:
                1. Test Duplicate Account Creation
                2. Test Unauthorized Account Creation
                3. Test Invalid Data (no title) Account Creation
    """

    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        super().setUp()
        self.url = "/auth/create_account"

        self.account_details = {
            "title": "TestAccount"
        }

        # Creating a user - since account creation requires a user
        self.user_details = {
            "fullName": "Test User",
            "email": "test@user.com",
            "username": "testuser",
            "password": "testpasssword"
        }
        user_query = f"g.addV('{User.LABEL}')" + \
            f".property('{self.partition_key}', '{User.LABEL}')"
        for prop, val in self.user_details.items():
            user_query += f".property('{prop}', '{val}')"
        result = client.submit(user_query).all().result()[0]
        self.user = User.vertex_to_instance(result)

    def test_successful_account_creation(self):
        """ Tests that the Account creation API can successfully create
            an account given valid data
        """
        token = create_access_token(identity=self.user)
        r = self.client.post(
            self.url,
            json=self.account_details,
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["title"], self.account_details["title"])
