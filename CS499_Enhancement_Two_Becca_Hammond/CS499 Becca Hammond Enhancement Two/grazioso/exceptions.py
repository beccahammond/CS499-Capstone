# Becca Hammond
# CS499 Enhancement One - Software Design and Engineering
# 11/15/2026
# Version 1.0
#
# Purpose: Custom exceptions for the Grazioso Salvare dashboard. The original
# CRUD module caught every database error and quietly returned False, an
# empty list or 0, so a failed query looked the same as a query with no
# results. These exceptions let each layer raise a clear error and let the
# dashboard decide what to show the user.


class GraziosoError(Exception):
    """ Base class for every error raised by this application """


class ConfigError(GraziosoError):
    """ A required setting is missing or invalid """


class DatabaseError(GraziosoError):
    """ A MongoDB operation failed """


class DatabaseUnavailableError(DatabaseError):
    """ The MongoDB server could not be reached """


class UnknownRescueTypeError(GraziosoError, ValueError):
    """ The dashboard was asked for a rescue type that does not exist """
