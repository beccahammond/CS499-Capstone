# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
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
#
# Changes in Version 2.0:
#   - iterate() streams documents from the cursor one at a time, so callers
#     can process large results in O(1) memory instead of building a list
#   - read_page() returns one page using keyset pagination on _id
#   - count() returns how many documents match, for the page count

import logging
from typing import Any, Dict, Iterator, List, Optional

from bson.objectid import ObjectId
from pymongo import ASCENDING, MongoClient
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

    # Stream matching documents one at a time.
    # read() builds the whole result into a list, which is O(n) memory. This
    # hands each document to the caller as the cursor fetches it, so the
    # caller only holds what it decides to keep, such as the top k in
    # ranking.py. Errors are still raised as DatabaseError, even partway
    # through the results.
    def iterate(self, query: dict, projection: Optional[dict] = None) -> Iterator[dict]:
        query = self._require_dict(query, "query")
        if projection is not None:
            projection = self._require_dict(projection, "projection")
        try:
            for document in self.collection.find(query, projection):
                yield document
        except PyMongoError as error:
            logger.error("Read failed for query %s: %s", query, error)
            raise DatabaseError("Could not read from the database.") from error

    # Return one page of results using keyset (range-based) pagination.
    #
    # The obvious way to page is skip(page * size).limit(size), but MongoDB
    # still walks past every skipped document, so page p costs O(p * size)
    # and the last page of 10,000 records costs about as much as loading them
    # all. Keyset pagination remembers the last _id on the previous page and
    # asks for _id values greater than it. _id always has an index, so each
    # page is an index seek plus page_size documents: O(log n + size).
    #
    # The trade-off is that you can only move from a page you have already
    # seen. Jumping straight to page 500 means walking forward to it.
    #
    # after_id: last _id from the previous page, or None for the first page
    # Returns (documents, last_id). last_id is None when there are no more pages.
    def read_page(self, query: dict, after_id: Optional[Any] = None, page_size: int = 10,
                  projection: Optional[dict] = None):
        query = self._require_dict(query, "query")
        if page_size <= 0:
            raise ValueError("`page_size` must be greater than 0")
        if projection is not None:
            projection = self._require_dict(projection, "projection")
            # _id is needed to know where the page ends, so it can't be left
            # out here. The caller removes it before display if it wants to.
            projection = {key: value for key, value in projection.items()
                          if not (key == "_id" and not value)} or None

        page_query = dict(query)
        if after_id is not None:
            if isinstance(after_id, str):
                after_id = ObjectId(after_id)
            # Combine with any existing filter instead of replacing it
            page_query = {"$and": [query, {"_id": {"$gt": after_id}}]} if query else {"_id": {"$gt": after_id}}

        try:
            cursor = (self.collection.find(page_query, projection)
                      .sort("_id", ASCENDING)
                      .limit(page_size))
            documents = list(cursor)
        except PyMongoError as error:
            logger.error("Page read failed for query %s: %s", query, error)
            raise DatabaseError("Could not read from the database.") from error

        last_id = documents[-1]["_id"] if len(documents) == page_size else None
        return documents, last_id

    # Count matching documents without loading them
    def count(self, query: dict) -> int:
        query = self._require_dict(query, "query")
        try:
            return int(self.collection.count_documents(query))
        except PyMongoError as error:
            logger.error("Count failed for query %s: %s", query, error)
            raise DatabaseError("Could not count documents.") from error

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
