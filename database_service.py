# database_service.py
from sqlmodel import SQLModel, create_engine, Session
from database_models import Quote, Order
import os
from typing import Dict, Any

class DatabaseService:
    def __init__(self, database_url: str = None):
        """
        Initialize the database service.

        Args:
            database_url: SQLAlchemy database URL. If None, uses Railway PostgreSQL.
        """
        if database_url is None:
            return RuntimeError("no database url provided")
        self.engine = create_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=300,  # Recycle connections every 5 minutes
        )
        self.database_url = database_url

    def create_tables(self) -> Dict[str, Any]:
        """
        Create all tables defined in database_models.py

        Returns:
            Dict with status and details about the operation
        """
        try:
            SQLModel.metadata.create_all(self.engine)
            return {
                "status": "success",
                "message": "All tables created successfully",
                "tables_created": ["quotes", "orders"],
                "database_url": self.database_url
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to create tables: {str(e)}",
                "error": str(e)
            }

    def reset_tables(self) -> Dict[str, Any]:
        """
        Drop all tables and recreate them (reset the database)

        Returns:
            Dict with status and details about the operation
        """
        try:
            # Drop all tables
            SQLModel.metadata.drop_all(self.engine)

            # Recreate all tables
            SQLModel.metadata.create_all(self.engine)

            return {
                "status": "success",
                "message": "Database reset successfully - all tables dropped and recreated",
                "tables_reset": ["quotes", "orders"],
                "database_url": self.database_url
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to reset database: {str(e)}",
                "error": str(e)
            }

    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the current database state

        Returns:
            Dict with database information
        """
        try:
            with Session(self.engine) as session:
                # Check if tables exist by trying to query them
                quote_count = session.query(Quote).count()
                order_count = session.query(Order).count()

                return {
                    "status": "success",
                    "database_url": self.database_url,
                    "tables": {
                        "quotes": {
                            "exists": True,
                            "record_count": quote_count
                        },
                        "orders": {
                            "exists": True,
                            "record_count": order_count
                        }
                    }
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to get database info: {str(e)}",
                "error": str(e),
                "database_url": self.database_url
            }

    def get_session(self) -> Session:
        """
        Get a database session for use in other services

        Returns:
            SQLModel Session object
        """
        return Session(self.engine)