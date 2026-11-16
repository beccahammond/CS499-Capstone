# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
# Original: ProjectTwoDashboard.ipynb, CS340 Project 2, 10/19/2025
#
# Purpose: Entry point for the Grazioso Salvare dashboard. Run it with
#     python app.py
# The original only ran inside a Jupyter notebook through JupyterDash and
# app.run_server(), which current versions of Dash no longer have. This file
# runs the dashboard as a standalone web app.
#
# Startup steps:
#   1. Load settings from the environment. Stop if anything required is missing.
#   2. Connect to MongoDB and ping it.
#   3. If the ping fails, show a "database unavailable" page instead of crashing.
#   4. Otherwise build the layout, register the callbacks and start the server.

import atexit
import logging
import sys
from pathlib import Path

from dash import Dash

from grazioso.callbacks import register_callbacks
from grazioso.config import AppConfig, load_config, setup_logging
from grazioso.data.animal_shelter import AnimalShelter
from grazioso.exceptions import ConfigError, DatabaseUnavailableError
from grazioso.layout import (LOGO_FILENAME, PAGE_TITLE, build_layout,
                             build_unavailable_layout, logo_exists)

logger = logging.getLogger(__name__)

ASSETS_FOLDER = str(Path(__file__).resolve().parent / "assets")


def create_app(shelter: AnimalShelter) -> Dash:
    """
    Build the Dash app around a connected AnimalShelter.
    Kept separate from main() so the tests can build the app with a
    mongomock database.
    """
    app = Dash(__name__, title=PAGE_TITLE, assets_folder=ASSETS_FOLDER)

    try:
        shelter.ping()
    except DatabaseUnavailableError as error:
        app.layout = build_unavailable_layout(str(error))
        return app

    logo_src = app.get_asset_url(LOGO_FILENAME) if logo_exists(ASSETS_FOLDER) else None
    app.layout = build_layout(logo_src)
    register_callbacks(app, shelter)
    return app


def connect(config: AppConfig) -> AnimalShelter:
    """ Create the CRUD object from the loaded settings """
    return AnimalShelter(config.db_user,
                         config.db_password,
                         host=config.db_host,
                         port=config.db_port,
                         db_name=config.db_name,
                         collection_name=config.collection_name,
                         auth_source=config.auth_source,
                         timeout_ms=config.timeout_ms)


def main() -> None:
    try:
        config = load_config()
    except ConfigError as error:
        setup_logging()
        logger.error("%s", error)
        sys.exit(1)

    setup_logging(config.log_level)
    logger.info("Starting dashboard with %r", config)

    shelter = connect(config)
    # Close the database connection when the server stops
    atexit.register(shelter.close)

    app = create_app(shelter)
    app.run(host=config.app_host, port=config.app_port, debug=config.debug)


if __name__ == "__main__":
    main()
