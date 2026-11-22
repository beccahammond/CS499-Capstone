# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Unit tests for the CRUD module. Covers each CRUD method, input
# validation, and the new error handling that replaced the silent failures.
# Version 2.0 adds tests for streaming, counting and keyset pagination.

from unittest.mock import MagicMock

import pytest
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from grazioso.data.animal_shelter import AnimalShelter
from grazioso.exceptions import DatabaseError, DatabaseUnavailableError


###########################
# Create
###########################
def test_create_inserts_document(shelter):
    assert shelter.create({"rec_num": 99, "name": "New Dog"}) is True
    assert shelter.read({"rec_num": 99})[0]["name"] == "New Dog"


@pytest.mark.parametrize("bad_document", [{}, None, "not a dict", ["list"]])
def test_create_rejects_bad_input(shelter, bad_document):
    with pytest.raises(ValueError):
        shelter.create(bad_document)


###########################
# Read
###########################
def test_read_returns_matching_documents(shelter):
    results = shelter.read({"breed": "Bloodhound"})
    assert [animal["name"] for animal in results] == ["Boomer"]


def test_read_with_empty_query_returns_everything(shelter):
    assert len(shelter.read({})) == 7


def test_read_with_no_matches_returns_empty_list(shelter):
    assert shelter.read({"breed": "Not A Breed"}) == []


def test_read_projection_leaves_out_id(shelter):
    results = shelter.read({"rec_num": 1}, {"_id": 0})
    assert "_id" not in results[0]
    assert results[0]["name"] == "Daisy"


@pytest.mark.parametrize("bad_query", [None, "breed", 5])
def test_read_rejects_bad_query(shelter, bad_query):
    with pytest.raises(ValueError):
        shelter.read(bad_query)


def test_read_rejects_bad_projection(shelter):
    with pytest.raises(ValueError):
        shelter.read({}, projection="name")


###########################
# Update
###########################
def test_update_many_returns_modified_count(shelter):
    assert shelter.update({"breed": "Labrador Retriever Mix"}, {"outcome_type": "Transfer"}) == 2


def test_update_one_changes_a_single_document(shelter):
    assert shelter.update({"breed": "Labrador Retriever Mix"}, {"outcome_type": "Transfer"}, many=False) == 1


def test_update_rejects_empty_new_values(shelter):
    with pytest.raises(ValueError):
        shelter.update({"rec_num": 1}, {})


###########################
# Delete
###########################
def test_delete_one_removes_a_single_document(shelter):
    assert shelter.delete({"breed": "Labrador Retriever Mix"}, many=False) == 1
    assert len(shelter.read({"breed": "Labrador Retriever Mix"})) == 1


def test_delete_many_removes_all_matches(shelter):
    assert shelter.delete({"animal_type": "Dog"}) == 6


def test_delete_rejects_bad_query(shelter):
    with pytest.raises(ValueError):
        shelter.delete("everything")


###########################
# Error handling
###########################
# The original returned False, [] or 0 when the database failed, which looked
# the same as a successful query with no results. These tests make sure a
# database failure now raises DatabaseError instead.
@pytest.fixture
def broken_shelter(mock_client):
    shelter = AnimalShelter("testuser", "testpass", client=mock_client)
    shelter.collection = MagicMock()
    for method in ("insert_one", "find", "update_many", "update_one", "delete_many",
                   "delete_one", "count_documents"):
        getattr(shelter.collection, method).side_effect = PyMongoError("connection lost")
    return shelter


def test_create_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        broken_shelter.create({"name": "Rex"})


def test_read_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        broken_shelter.read({})


def test_update_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        broken_shelter.update({}, {"name": "Rex"})


def test_delete_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        broken_shelter.delete({"name": "Rex"})


def test_database_error_is_logged(broken_shelter, caplog):
    with pytest.raises(DatabaseError):
        broken_shelter.read({"breed": "Rottweiler"})
    assert "Read failed" in caplog.text


###########################
# Connection
###########################
def test_ping_succeeds_when_server_is_up(shelter):
    shelter.ping()


def test_ping_raises_when_server_is_down():
    client = MagicMock()
    client.admin.command.side_effect = ServerSelectionTimeoutError("no server")
    shelter = AnimalShelter("testuser", "testpass", client=client)
    with pytest.raises(DatabaseUnavailableError):
        shelter.ping()


def test_close_closes_the_client():
    client = MagicMock()
    AnimalShelter("testuser", "testpass", client=client).close()
    client.close.assert_called_once()


def test_real_client_gets_credentials_and_timeout(monkeypatch):
    # Check that a real MongoClient is created with the login passed as
    # arguments and a timeout, without connecting to anything.
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("grazioso.data.animal_shelter.MongoClient", fake_client)
    AnimalShelter("aacuser", "p@ss:word", host="db.example", port=27018, timeout_ms=2000)

    assert captured["username"] == "aacuser"
    assert captured["password"] == "p@ss:word"
    assert captured["host"] == "db.example"
    assert captured["port"] == 27018
    assert captured["serverSelectionTimeoutMS"] == 2000
    assert captured["authSource"] == "admin"


###########################
# Streaming, counting and pagination (Version 2.0)
###########################
def test_iterate_yields_matching_documents(shelter):
    names = [dog["name"] for dog in shelter.iterate({"breed": "Rottweiler"}, {"_id": 0})]
    assert names == ["Zeke", "Ghost"]


def test_iterate_is_lazy(shelter):
    # Nothing is read until the caller asks for the next document
    stream = shelter.iterate({})
    assert next(stream)["rec_num"] == 1


def test_iterate_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        list(broken_shelter.iterate({}))


def test_count(shelter):
    assert shelter.count({}) == 7
    assert shelter.count({"animal_type": "Cat"}) == 1


def test_count_raises_database_error(broken_shelter):
    with pytest.raises(DatabaseError):
        broken_shelter.count({})


def test_read_page_walks_every_document_once(shelter):
    seen, after_id = [], None
    while True:
        documents, after_id = shelter.read_page({}, after_id, page_size=3)
        seen.extend(doc["rec_num"] for doc in documents)
        if after_id is None:
            break
    assert sorted(seen) == [1, 2, 3, 4, 5, 6, 7]
    assert len(seen) == len(set(seen))


def test_read_page_respects_the_query(shelter):
    documents, _ = shelter.read_page({"animal_type": "Dog"}, None, page_size=10)
    assert all(doc["animal_type"] == "Dog" for doc in documents)
    assert len(documents) == 6


def test_read_page_accepts_string_cursor(shelter):
    first, last_id = shelter.read_page({}, None, page_size=2)
    second, _ = shelter.read_page({}, str(last_id), page_size=2)
    assert {doc["rec_num"] for doc in first}.isdisjoint(doc["rec_num"] for doc in second)


def test_read_page_keeps_id_for_the_cursor(shelter):
    documents, last_id = shelter.read_page({}, None, page_size=2, projection={"_id": 0, "name": 1})
    assert last_id == documents[-1]["_id"]


def test_read_page_rejects_bad_page_size(shelter):
    with pytest.raises(ValueError):
        shelter.read_page({}, None, page_size=0)
