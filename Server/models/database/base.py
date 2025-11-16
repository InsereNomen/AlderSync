"""
AlderSync Server - Database Base

Shared declarative base for all SQLAlchemy models.
This ensures all models share the same metadata and can reference each other.
"""

from sqlalchemy.orm import declarative_base

# Create the shared declarative base
Base = declarative_base()
