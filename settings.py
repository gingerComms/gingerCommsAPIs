import os


# DATABASE_SETTINGS = {
#     "host": os.environ.get("DB_HOST", "ws://localhost:8901/"),
#     "traversal_source": "g",
#     "username": os.environ.get("DB_USERNAME", "/dbs/tasks/colls/items"),
#     "password": os.environ.get("DB_PASSWORD",
#                                "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2n" +
#                                "Q9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="),
#     "partition_key": os.environ.get("DB_PARTITION_KEY", "category")
# }

DATABASE_SETTINGS = {
    "host": os.environ.get("DB_HOST", "wss://gingercomms.gremlin.cosmos.azure.com/"),
    "traversal_source": "g",
    "port": 443,
    "username": os.environ.get("DB_USERNAME", "/dbs/gingerDB/colls/gingerGraph"),
    "password": os.environ.get("DB_PASSWORD",
                               "YsvknCu93dwflesfg9H4E5GDWxBps97dkCWhvvWrb" +
                               "QRMQQG2FO0e8VDBVdIy3HWfSrwWJx5a7jmWvTsMYgVRBw=="),
    "partition_key": os.environ.get("DB_PARTITION_KEY", "topic")
}

SECRET_KEY = os.environ.get("SECRET_KEY", "secret-key")
