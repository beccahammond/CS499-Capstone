# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Unit tests for loading settings from the environment.

import pytest

from grazioso.config import load_config
from grazioso.exceptions import ConfigError

REQUIRED = {"DB_USER": "aacuser", "DB_PASSWORD": "secret"}


def test_defaults_are_used_when_only_required_settings_are_set():
    config = load_config(REQUIRED)
    assert config.db_user == "aacuser"
    assert config.db_host == "localhost"
    assert config.db_port == 27017
    assert config.db_name == "aac"
    assert config.collection_name == "animals"
    assert config.timeout_ms == 5000
    assert config.debug is False


def test_settings_can_be_overridden():
    config = load_config({**REQUIRED, "DB_HOST": "db.example", "DB_PORT": "27018",
                          "DB_TIMEOUT_MS": "2000", "APP_DEBUG": "true", "LOG_LEVEL": "debug"})
    assert config.db_host == "db.example"
    assert config.db_port == 27018
    assert config.timeout_ms == 2000
    assert config.debug is True
    assert config.log_level == "DEBUG"


@pytest.mark.parametrize("missing", ["DB_USER", "DB_PASSWORD"])
def test_missing_required_setting_raises(missing):
    env = {key: value for key, value in REQUIRED.items() if key != missing}
    with pytest.raises(ConfigError, match=missing):
        load_config(env)


@pytest.mark.parametrize("bad_port", ["abc", "0", "-5"])
def test_bad_port_raises(bad_port):
    with pytest.raises(ConfigError, match="DB_PORT"):
        load_config({**REQUIRED, "DB_PORT": bad_port})


def test_password_never_shows_in_repr():
    assert "secret" not in repr(load_config(REQUIRED))
