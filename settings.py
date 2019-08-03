import os


DATABASE_SETTINGS = {
    "host": os.environ.get("DB_HOST", "ws://localhost:8901/"),
    "traversal_source": "g",
    "username": os.environ.get("DB_USERNAME", "/dbs/tasks/colls/items"),
    "password": os.environ.get("DB_PASSWORD",
                               "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2n" +
                               "Q9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw=="),
    "partition_key": os.environ.get("DB_PARTITION_KEY", "category")
}

SECRET_KEY = os.environ.get("SECRET_KEY", "secret-key")
