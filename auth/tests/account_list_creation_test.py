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
        self.url = "/auth/accounts/"

        self.account_details = {
            "title": "TestAccount"
        }

        # Creating a user - since account creation requires a user
        self.user = User.create(**{
            "username": "TestU",
            "email": "TestEmail@g.com",
            "password": "Test",
            "fullName": "Test 2"
        })

    def test_account_list(self):
        """ Tests the LIST GET API for Accounts """
        token = create_access_token(identity=self.user)

        account = Account.create(**self.account_details)
        account_edge = UserHoldsAccount.create(
            user=self.user.id, account=account.id, relationType="secondary")

        r = self.client.get(
            self.url,
            headers=self.generate_headers(token)
        )
        
        raise ValueError(r.json)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json), 1)

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
