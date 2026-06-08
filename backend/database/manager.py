import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_folder = os.getenv("DATABASE_FOLDER", "./databases")
        # Ensure folder exists
        if not os.path.exists(self.db_folder):
            os.makedirs(self.db_folder)
            
        self.current_db_id = None
        self._engine = None
        self._SessionLocal = None
        
        # Initial discovery
        dbs = self.list_databases()
        if dbs:
            self.current_db_id = dbs[0]["id"]
            self._initialize_engine()

    def _initialize_engine(self):
        if not self.current_db_id:
            return
            
        db_path = os.path.join(self.db_folder, self.current_db_id)
        if not os.path.exists(db_path):
            logger.error(f"Database file {db_path} not found.")
            return

        url = f"sqlite:///{db_path}"
        connect_args = {"check_same_thread": False}
        
        self._engine = create_engine(url, connect_args=connect_args)
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        logger.info(f"Initialized engine for database: {self.current_db_id}")

    def get_database_config(self, db_id: str) -> Optional[Dict]:
        """
        id here is the filename (e.g. sales.db)
        """
        db_path = os.path.join(self.db_folder, db_id)
        if os.path.exists(db_path):
            return {
                "id": db_id,
                "name": db_id,
                "connection": f"sqlite:///{db_path}"
            }
        return None

    def set_database(self, db_id: str):
        if self.current_db_id == db_id:
            return self.get_database_config(db_id)
        
        db_config = self.get_database_config(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found in {self.db_folder}")
        
        self.current_db_id = db_id
        self._initialize_engine()
        return db_config

    @property
    def engine(self):
        return self._engine

    def get_session(self):
        if not self._SessionLocal:
            self._initialize_engine()
        if not self._SessionLocal:
            return None
        return self._SessionLocal()

    def list_databases(self) -> List[Dict]:
        """
        Scans the DATABASE_FOLDER for .db files.
        """
        if not os.path.exists(self.db_folder):
            return []
            
        files = [f for f in os.listdir(self.db_folder) if f.endswith(".db")]
        return [
            {"id": f, "name": f} 
            for f in sorted(files)
        ]

db_manager = DatabaseManager()
