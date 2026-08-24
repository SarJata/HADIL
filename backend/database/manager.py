import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.db_folder = os.getenv("DATABASE_FOLDER", "./databases")
        if not os.path.exists(self.db_folder):
            os.makedirs(self.db_folder)
            
        self.current_db_id = None
        self.current_db_name = None
        self.custom_connection_uri = None
        self._engine = None
        self._SessionLocal = None
        
        # Initial discovery of local .db files
        dbs = self.list_databases()
        if dbs:
            self.current_db_id = dbs[0]["id"]
            self.current_db_name = dbs[0]["name"]
            self._initialize_engine()

    def _initialize_engine(self):
        if self.custom_connection_uri:
            url = self.custom_connection_uri
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        elif self.current_db_id:
            db_path = os.path.join(self.db_folder, self.current_db_id)
            if not os.path.exists(db_path):
                logger.error(f"Database file {db_path} not found.")
                return
            url = f"sqlite:///{db_path}"
            connect_args = {"check_same_thread": False}
        else:
            return

        try:
            self._engine = create_engine(url, connect_args=connect_args)
            self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
            logger.info(f"Initialized engine for database: {self.current_db_name or self.current_db_id}")
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            self._engine = None
            self._SessionLocal = None

    def test_connection(self, connection_uri: str) -> Dict[str, Any]:
        """
        Attempts to connect to a database URI safely without exposing passwords.
        """
        try:
            connect_args = {"check_same_thread": False} if connection_uri.startswith("sqlite") else {}
            temp_engine = create_engine(connection_uri, connect_args=connect_args)
            with temp_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            temp_engine.dispose()
            return {"success": True, "message": "Connection successful"}
        except Exception as e:
            logger.error(f"Test connection error: {e}")
            # Sanitize error message to prevent password leakage
            err_msg = str(e)
            if "password" in err_msg.lower() or "denied" in err_msg.lower():
                user_msg = "Access denied or authentication failed. Please check your username and password."
            elif "operationalerror" in err_msg.lower() or "connect" in err_msg.lower():
                user_msg = "Could not connect to database host. Please verify server address and port."
            elif "driver" in err_msg.lower() or "module" in err_msg.lower():
                user_msg = "Required database driver is not installed on the backend server."
            else:
                user_msg = "Could not establish database connection. Please check connection string format."
            return {"success": False, "message": user_msg}

    def set_custom_connection(self, connection_uri: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Connects HADIL to a remote or custom SQLAlchemy database URI.
        """
        test_res = self.test_connection(connection_uri)
        if not test_res["success"]:
            raise ValueError(test_res["message"])

        self.custom_connection_uri = connection_uri
        self.current_db_id = name or "custom_db"
        self.current_db_name = name or "Remote Database"
        self._initialize_engine()
        return {
            "id": self.current_db_id,
            "name": self.current_db_name,
            "connection": "custom"
        }

    def get_database_config(self, db_id: str) -> Optional[Dict]:
        if self.custom_connection_uri and self.current_db_id == db_id:
            return {
                "id": self.current_db_id,
                "name": self.current_db_name or self.current_db_id,
                "connection": "custom"
            }
        db_path = os.path.join(self.db_folder, db_id)
        if os.path.exists(db_path):
            return {
                "id": db_id,
                "name": db_id,
                "connection": f"sqlite:///{db_path}"
            }
        return None

    def set_database(self, db_id: str):
        # Reset custom connection if selecting a local .db file
        self.custom_connection_uri = None
        db_config = self.get_database_config(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found in {self.db_folder}")
        
        self.current_db_id = db_id
        self.current_db_name = db_id
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

    def get_current_display_name(self) -> str:
        if self.current_db_name:
            return self.current_db_name
        return self.current_db_id or "Not Connected"

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
