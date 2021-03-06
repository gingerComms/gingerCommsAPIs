# gingerCommsAPIs

Backend for the GingerCommsAPI - written in Python3 using Flask

## Installation

- All of the Python dependencies can be installed using the provided `requirements.txt` file, with `pip`
- Since the app currently depends on a Gremlin database, the route for the database can be provided in the os environments listed in the `settings.py` file's `DATABASE_SETTINGS` variable
	- For starting an instance of the Azure CosmosDB Emulator locally, [the following method can be used](https://github.com/MichalWierzbinski/cosmosdb-emulator-gremlin/blob/master/README.md) after installing the Emulator normally (ignoring the first two steps) 

## Running Tests

All of the included unit tests can be run using unittest's discover utility:

``` python -m unittest discover . "*_test.py" ```

## Running Debug Server

The following can be run from within the main package to start the debug flask server:

```
set FLASK_APP=api.py # (or export FLASK_APP=api.py for UNIX systems)
flask run
```

## TODO

- [ ] Mixin for generic GET List views that would use a class attribute/function to generate a list of "Vertices" and a serializer attribute and return the serialized data to the user through the "get" endpoint
- [ ] Mixin for generic GET Detail views that would use a class attribute/function to "get" a single Vertex and a serializer attribute and return the serialized data to the user through the "get" endpoint