# Becca Hammond
# CS499 Enhancement Two - Algorithms and Data Structures
# 11/16/2026
# Version 2.0
# Version 1.0 (11/15/2026): Enhancement One, Software Design and Engineering
#
# Purpose: Marks the grazioso folder as a Python package. The dashboard is
# split into modules so each piece has one job:
#   config.py                  - loads settings from environment variables
#   exceptions.py              - custom errors used across the app
#   data/animal_shelter.py     - CRUD module for MongoDB (model)
#   services/rescue_filters.py - rescue type criteria (business rules)
#   services/ranking.py        - suitability scoring and top-k ranking
#   services/cache.py          - least-recently-used cache with expiry
#   layout.py                  - Dash page layout (view)
#   callbacks.py               - Dash callbacks (controller)

__version__ = "2.0"
