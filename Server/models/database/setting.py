"""
AlderSync Server - Setting Database Model

Setting model for storing server configuration as key-value pairs.
Specification.md section 6.4
"""

from sqlalchemy import Column, String

from models.database.base import Base


class Setting(Base):
    """
    Settings table - stores server configuration as key-value pairs
    Specification.md section 6.4
    """
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
