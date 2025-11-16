"""
AlderSync Server - Database Module

This module exports the global db_manager instance for use across the application.
"""

from managers.database_manager import DatabaseManager

# Global database manager instance
# Initialized in server.py lifespan handler
db_manager: DatabaseManager = None
