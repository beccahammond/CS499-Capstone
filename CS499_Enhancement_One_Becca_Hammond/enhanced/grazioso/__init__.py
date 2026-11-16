# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Marks the grazioso folder as a Python package. The dashboard is
# split into modules so each piece has one job:
#   config.py                  - loads settings from environment variables
#   exceptions.py              - custom errors used across the app
#   data/animal_shelter.py     - CRUD module for MongoDB (model)
#   services/rescue_filters.py - rescue type criteria (business rules)
#   layout.py                  - Dash page layout (view)
#   callbacks.py               - Dash callbacks (controller)

__version__ = "1.0"
