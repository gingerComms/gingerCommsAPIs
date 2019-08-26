from utils.flask_test_case import FlaskTestCase
from db.engine import client
from auth.models import *
import json


class UserRegistrationTestCase(FlaskTestCase):
    """ Contains all of the individual test cases for a successful and
        unsuccessful user registration
    """

    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        super().setUp()
        self.url = "/auth/register"

        self.user_details = {
            "fullName": "Test User",
            "email": "test@user.com",
            "username": "testuser",
            "password": "testpasssword"
        }
        # Create query for the user with the above details
        self.create_query = f"g.addV('{User.LABEL}')" + \
            f".property('{self.partition_key}', '{User.LABEL}')"
        for prop, val in self.user_details.items():
            self.create_query += f".property('{prop}', '{val}')"

    def test_user_registration_with_duplicate_username(self):
        """ Tests the user registration endpoint to confirm that
            a user can't be created with an existing username
        """
        # Creating the base user that will be tested against
        result = client.submit(self.create_query).all().result()
        assert result, ValueError("Test Error - Could not "
                                  "create user manually!")

        # Changing the email to confirm the username duplication is checked
        self.user_details["email"] = "test@user2.com"

        r = self.client.post(self.url, json=self.user_details)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json["error"], "User already exists!")

    def test_user_registration_with_duplicate_email(self):
        """ Tests the user registration endpoint to confirm that
            a user can't be created with an existing email
        """
        # Creating the base user that will be tested against
        result = client.submit(self.create_query).all().result()
        assert result, ValueError("Test Error - Could not "
                                  "create user manually!")

        # Changing the username to confirm the email duplication is checked
        self.user_details["username"] = "testuser2"

        r = self.client.post(self.url, json=self.user_details)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json["error"], "User already exists!")

    def test_successful_user_registration(self):
        """ Tests that the user registration endpoint works successfully
            given a set of normal user data

            - Asserts that an account is automatically created for the user
                on successful registration
        """
        r = self.client.post(self.url, json=self.user_details)

        self.assertEqual(r.status_code, 201)
        self.assertIn("user", r.json)
        self.assertIn("token", r.json)

        # Confirming that an account was created
        required_account_title = f"myaccount@{self.user_details['username']}"
        account_query = f"g.V().has('{Account.LABEL}', 'title', " + \
            f"'{required_account_title}').as('a')" + \
            f".in('{UserHoldsAccount.LABEL}')" + \
            f".has('{User.LABEL}', 'username', " + \
            f"'{self.user_details['username']}').select('a')"
        results = client.submit(account_query).all().result()
        self.assertEqual(len(results), 1, "Account not created/not linked!")
