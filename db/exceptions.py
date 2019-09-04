""" Provides all custom exceptions that may be raised during typical
    database processes
"""


class DatabaseException(Exception):
    """ Exception that all database related exceptions are based off of """
    def __init__(self, message):
        self.message = message
        super().__init__(message) 


class CustomValidationFailedException(DatabaseException):
    """ Raised during instance creation when validation fails during the
        `custom_validation` method
    """
    def __init__(self, message):
        super().__init__(message)


class ObjectCanNotBeDeletedException(DatabaseException):
    """ Raised during instance deletion in case a vertex/edge should
        not be able to be deleted
    """
    def __init__(self, message):
        super().__init__(message)
