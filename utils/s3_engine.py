import boto3
import os
import base64
from passlib.hash import sha256_crypt


def establish_conn(resource_name):
    """ Establishes and returns a resource object through the credentials
        present in the environment
    """
    AWS_CREDS = {
        "aws_secret_access_key": os.environ["AWS_SECRET"],
        "aws_access_key_id": os.environ["AWS_ACCESS"],
        "region_name": "ap-southeast-2"
    }
    session = boto3.session.Session(**AWS_CREDS)
    client = session.client(
        resource_name, config=boto3.session.Config(signature_version='s3v4'))

    return client


class S3Engine:
    """ An S3 engine class used for:
        - Generating presigned upload/retrieval URL
        - Deleting
        files in a provided bucket
    """
    def __init__(self, bucket_name=os.environ["AWS_BUCKET"]):
        """ Initializes the s3 client """
        self.client = establish_conn("s3")
        self.bucket_name = bucket_name

    def generate_sse_key(password):
        """ Generates sse base64 encoded key from password """
        password = sha256_crypt.using(salt="hashsalt", rounds=1000).hash(password)
        password = password[0:32]
        key = base64.b64encode(password.encode("utf-8"))
        return key.decode("utf-8")


    def generate_sse_md5_key(password):
        """ Generates md5 key from password """
        password = sha256_crypt.using(salt="hashsalt", rounds=1000).hash(password)
        password = password[0:32]
        md5 = base64.b64encode(hashlib.md5(password.encode("utf-8")).digest())
        return md5.decode("utf-8")

    def generate_presigned_post(self, filename, password):
        """ Generates a presigned URL for the given client method with
            the given params
        """
        url = self.client.generate_presigned_post(self.bucket_name, filename)
        return url

    def generate_presigned_get_url(self, filename, password):
        params = {
            "Bucket": self.bucket_name,
            "Key": filename
        }
        return self.client.generate_presigned_url("get_object", params, 300)

    def delete_file(self, filename, password):
        """ Deletes the specified file from the s3 bucket """
        self.client.delete_object(
            Bucket=self.bucket_name,
            Key=f"{filename}"
        )
