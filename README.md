# gingerCommsAPIs

Backend for the GingerCommsAPI - written in Python3 using Flask

## Installation

- All of the Python dependencies can be installed using the provided `requirements.txt` file, with `pip`
- Since the app currently depends on a Gremlin database, the route for the database can be provided in the os environments listed in the `settings.py` file's `DATABASE_SETTINGS` variable
	- For starting an instance of the Azure CosmosDB Emulator locally, [the following method can be used](https://github.com/MichalWierzbinski/cosmosdb-emulator-gremlin/blob/master/README.md) after installing the Emulator normally (ignoring the first two steps) 

# Running Tests

All of the included unit tests can be run using the provided `tests.py` file by running `python tests.py`
