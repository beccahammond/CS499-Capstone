# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
# Original: CRUD_Python_Module_5.py, CS340 Module 5 Project 1, 10/5/2025
#
# Purpose: CRUD module for the animals collection in the aac MongoDB database.
# This is the model in the dashboard's Model-View-Controller design. The
# dashboard and the tests call these methods instead of talking to PyMongo
# directly.
#
# Changes from the original:
#   - Credentials are passed to MongoClient as arguments instead of being
#     built into the connection string
#   - Connections have a timeout, and ping() checks the server at startup
#   - Errors are logged and raised as DatabaseError instead of being hidden
#     behind False, [] or 0
#   - read() accepts a projection, which the original design asked for
#   - Every method validates its input the same way
#   - A client can be passed in, so the tests can use mongomock

import logging
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from grazioso.exceptions import DatabaseError, DatabaseUnavailableError

logger = logging.getLogger(__name__)


class AnimalShelter(object):
    """ CRUD operations for Animal collection in MongoDB """

    def __init__(self,
                 user: str,
                 password: str,
                 host: str = 'localhost',
                 port: int = 27017,
                 db_name: str = 'aac',
                 collection_name: str = 'animals',
                 auth_source: str = 'admin',
                 timeout_ms: int = 5000,
                 client: Optional[MongoClient] = None):

        # Initialize Connection
        #
        # Passing the username and password as arguments means PyMongo
        # handles the encoding. Building them into a mongodb:// string, like
        # the original did, breaks when a password has an @ or : in it.
        #
        # client lets the tests hand in a mongomock client instead of a real
        # server. In normal use it is left as None.
        if client is None:
            client = MongoClient(host=host,
                                 port=port,
                                 username=user,
                                 password=password,
                                 authSource=auth_source,
                                 serverSelectionTimeoutMS=timeout_ms)
        self.client = client
        self.database = self.client[db_name]
        self.collection = self.database[collection_name]

    # Check that the server is reachable before the dashboard starts.
    # Raises DatabaseUnavailableError instead of letting the first query hang.
    def ping(self) -> None:
        try:
            self.client.admin.command('ping')
        except PyMongoError as error:
            logger.error("MongoDB is not reachable: %s", error)
            raise DatabaseUnavailableError("Could not connect to the database.") from error

    # Shared input check for every method. The original checked inputs two
    # different ways depending on the method.
    @staticmethod
    def _require_dict(value: Any, name: str, allow_empty: bool = True) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError(f"`{name}` must be a dict")
        if not allow_empty and not value:
            raise ValueError(f"`{name}` must be a non-empty dict")
        return value

    # Implement the C Create in CRUD. Insert a single document.
    # Returns True if the insert succeeds. Raises DatabaseError if it fails.
    def create(self, document: dict) -> bool:
        document = self._require_dict(document, "document", allow_empty=False)
        try:
            result = self.collection.insert_one(document)
            return bool(result.inserted_id)
        except PyMongoError as error:
            logger.error("Create failed: %s", error)
            raise DatabaseError("Could not insert the document.") from error

    # Implement the R Read in CRUD.
    # query is the key/value lookup for find(). projection picks which fields
    # come back, for example {'_id': 0} to leave out the ObjectId that the
    # data table can't display.
    def read(self, query: dict, projection: Optional[dict] = None) -> List[dict]:
        query = self._require_dict(query, "query")
        if projection is not None:
            projection = self._require_dict(projection, "projection")
        try:
            cursor = self.collection.find(query, projection)
            return list(cursor)
        except PyMongoError as error:
            logger.error("Read failed for query %s: %s", query, error)
            raise DatabaseError("Could not read from the database.") from error

    # Implement the U Update in CRUD.
    # query: MongoDB filter dict (e.g., {"name": "Lucy"})
    # new_values: fields to set (e.g., {"outcome_type": "Adoption"})
    # many: True -> update_many, False -> update_one
    # Returns the number of documents modified.
    def update(self, query: dict, new_values: dict, many: bool = True) -> int:
        query = self._require_dict(query, "query")
        new_values = self._require_dict(new_values, "new_values", allow_empty=False)
        try:
            if many:
                result = self.collection.update_many(query, {"$set": new_values})
            else:
                result = self.collection.update_one(query, {"$set": new_values})
            return int(result.modified_count)
        except PyMongoError as error:
            logger.error("Update failed for query %s: %s", query, error)
            raise DatabaseError("Could not update the documents.") from error

    # Implement the D Delete in CRUD.
    # query: MongoDB filter dict (e.g., {"rec_num": 123})
    # many: True -> delete_many, False -> delete_one
    # Returns the number of documents deleted.
    def delete(self, query: dict, many: bool = True) -> int:
        query = self._require_dict(query, "query")
        try:
            if many:
                result = self.collection.delete_many(query)
            else:
                result = self.collection.delete_one(query)
            return int(result.deleted_count)
        except PyMongoError as error:
            logger.error("Delete failed for query %s: %s", query, error)
            raise DatabaseError("Could not delete the documents.") from error

    # Close the connection when the app shuts down. The original never
    # closed its client.
    def close(self) -> None:
        self.client.close()
