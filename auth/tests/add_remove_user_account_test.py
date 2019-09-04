from utils.flask_test_case import FlaskTestCase
from flask_jwt_extended import create_access_token
from auth.models import *
from db.engine import client
import copy


class AddRemoveUserAccountTestCase(FlaskTestCase):
    """ Contains all of the test cases to confirm that:
        1) Only a User holding an account (through primary/secondary edge)
            can add new Users to the Account, and;
        2) User can be added to infinite number of accounts with a
            "secondary" edge (UserHoldsAccount)
        3) A User can not be removed from an Account it is holding through
            a primary relationship
    """
    def create_user_with_details(self, user_details):
        """ Submits a Gremlin query for creating a new user vertex
            with the given details
        """
        return User.create(**user_details)

    def create_account_edge(self, user, account, edge_type="primary"):
        """ Creates the UserHoldsAccount edge between the given
            user and account
        """
        edge = UserHoldsAccount.create(
            user=user.id, account=account.id, relationType=edge_type)

        return edge

    def setUp(self):
        """ Fixtures for the test cases;
            variables that remain the same for all of the test cases
        """
        super().setUp()
        self.url = "/auth/account/{account_id}/add_remove_user"

        self.holding_user_details = {
            "fullName": "Test User",
            "email": "test@user.com",
            "username": "testuser",
            "password": "testpasssword"
        }
        self.holding_user = self.create_user_with_details(
            self.holding_user_details)

        self.new_user_details = copy.copy(self.holding_user_details)
        self.new_user_details["email"] = "test@user2.com"
        self.new_user = self.create_user_with_details(self.new_user_details)

        self.account_1 = Account.create(title="Account1")
        self.account_2 = Account.create(title="Account2")

    def test_only_holding_user_can_add_user(self):
        """ Tests that the user can only be added to an account by users
            holding that account
        """
        url = self.url.format(account_id=self.account_1.id)
        token = create_access_token(identity=self.holding_user)

        # Unauthorized (401) request
        r = self.client.put(
            url,
            json={
                "user": self.new_user.id
            }
        )
        self.assertEqual(r.status_code, 401, r.data)

        # Forbidden (Authenticated but User doesn't hold account request)
        r = self.client.put(
            url,
            json={
                "user": self.new_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 403)

        # Successful (User holds account + is authenticated)
        self.create_account_edge(self.holding_user, self.account_1)
        r = self.client.put(
            url,
            json={
                "user": self.new_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 200)

    def test_user_can_be_added_to_infinite_secondary_accounts(self):
        """ Tests that the user can be inserted into an infinite number of
            accounts with a primary relationship
        """
        self.create_account_edge(self.holding_user, self.account_1)
        self.create_account_edge(self.holding_user, self.account_2)
        token = create_access_token(identity=self.holding_user)

        # Adding to the first account
        r = self.client.put(
            self.url.format(account_id=self.account_1.id),
            json={
                "user": self.new_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 200)

        # Adding to the second account
        r = self.client.put(
            self.url.format(account_id=self.account_2.id),
            json={
                "user": self.new_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 200)

    def test_user_cannot_be_removed_from_primary_account(self):
        """ Asserts that the user can not be removed from an account it holds
            through a primary edge
        """
        self.create_account_edge(self.holding_user, self.account_1)
        token = create_access_token(identity=self.holding_user)

        # Failure test - user can not be removed from primary account
        r = self.client.delete(
            self.url.format(account_id=self.account_1.id),
            json={
                "user": self.holding_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 400)

        # Success test - user can be removed from secondary account
        self.create_account_edge(self.new_user, self.account_1, "secondary")
        r = self.client.delete(
            self.url.format(account_id=self.account_1.id),
            json={
                "user": self.new_user.id
            },
            headers=self.generate_headers(token)
        )
        self.assertEqual(r.status_code, 200, r.json)
