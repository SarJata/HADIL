import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

def normalize_db_uri(uri: str) -> str:
    """
    Normalizes database connection URIs so MySQL connections consistently use PyMySQL
    driver on Windows and avoid requiring MySQLdb (mysqlclient).
    """
    if not uri:
        return uri
    clean_uri = uri.strip()
    if clean_uri.startswith("mysql+mysqldb://"):
        return clean_uri.replace("mysql+mysqldb://", "mysql+pymysql://", 1)
    elif clean_uri.startswith("mysql://"):
        return clean_uri.replace("mysql://", "mysql+pymysql://", 1)
    return clean_uri


from utils.path_resolver import get_default_database_folder

class DatabaseManager:
    def __init__(self):
        self.db_folder = get_default_database_folder()
        if not os.path.exists(self.db_folder):
            os.makedirs(self.db_folder, exist_ok=True)
            
        self.current_db_id = None
        self.current_db_name = None
        self.custom_connection_uri = None
        self._engine = None
        self._SessionLocal = None
        
        # Initial discovery: Prefer local SQLite database file if available, otherwise do not auto-connect remote RDBMS
        dbs = self.list_databases()
        valid_local_dbs = [
            d for d in dbs 
            if d.get("type") == "sqlite" and self.get_database_config(d["id"]) is not None
        ]
        if valid_local_dbs:
            try:
                self.set_database(valid_local_dbs[0]["id"])
            except Exception as e:
                logger.warning(f"Could not auto-select initial local database '{valid_local_dbs[0]['id']}': {e}")




    def _initialize_engine(self):
        if self.custom_connection_uri:
            url = normalize_db_uri(self.custom_connection_uri)
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        elif self.current_db_id:
            config = self.get_database_config(self.current_db_id)
            if not config or not config.get("connection"):
                logger.error(f"Database configuration for '{self.current_db_id}' not found.")
                self._engine = None
                self._SessionLocal = None
                return
            
            if config["connection"] == "custom":
                if not self.custom_connection_uri:
                    logger.error(f"Custom connection URI missing for database '{self.current_db_id}'.")
                    self._engine = None
                    self._SessionLocal = None
                    return
                url = normalize_db_uri(self.custom_connection_uri)
            else:
                url = normalize_db_uri(config["connection"])

            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        else:
            self._engine = None
            self._SessionLocal = None
            return

        try:
            self._engine = create_engine(url, connect_args=connect_args)
            self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
            logger.info(f"Initialized engine for database: {self.current_db_name or self.current_db_id}")

            
            # Register in HADIL Metadata DB
            db_type = "sqlite" if url.startswith("sqlite") else self._engine.name
            try:
                from services.metadata_service import metadata_service
                metadata_service.register_or_update_database(
                    db_id=self.current_db_id,
                    name=self.current_db_name or self.current_db_id,
                    database_type=db_type,
                    connection_uri=url if not url.startswith("sqlite") else None
                )
            except Exception as meta_err:
                logger.warning(f"Could not sync active database to HADIL Metadata DB: {meta_err}")
        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            self._engine = None
            self._SessionLocal = None

    def test_connection(self, connection_uri: str) -> Dict[str, Any]:
        """
        Attempts to connect to a database URI safely without exposing passwords.
        """
        try:
            normalized_uri = normalize_db_uri(connection_uri)
            connect_args = {"check_same_thread": False} if normalized_uri.startswith("sqlite") else {}
            temp_engine = create_engine(normalized_uri, connect_args=connect_args)
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

        self.custom_connection_uri = normalize_db_uri(connection_uri)

        self.current_db_id = name or "custom_db"
        self.current_db_name = name or "Remote Database"
        self._initialize_engine()
        return {
            "id": self.current_db_id,
            "name": self.current_db_name,
            "connection": "custom"
        }

    def get_database_config(self, db_id: str) -> Optional[Dict]:
        search_dirs = [self.db_folder]
        try:
            from services.metadata_service import metadata_service
            for d in metadata_service.list_db_directories():
                if d not in search_dirs and os.path.exists(d):
                    search_dirs.append(d)
        except Exception:
            pass

        for folder in search_dirs:
            db_path = os.path.join(folder, db_id)
            if os.path.exists(db_path):
                return {
                    "id": db_id,
                    "name": db_id,
                    "connection": f"sqlite:///{db_path}"
                }

        # Check registered metadata database table for remote RDBMS connections
        try:
            from services.metadata_service import metadata_service
            meta_db = metadata_service.get_database(db_id)
            if meta_db:
                decrypted_uri = metadata_service.get_decrypted_connection_uri(db_id)
                if decrypted_uri:
                    return {
                        "id": meta_db.id,
                        "name": meta_db.name,
                        "connection": decrypted_uri,
                        "database_type": meta_db.database_type
                    }
        except Exception as e:
            logger.warning(f"Could not check registered database metadata for {db_id}: {e}")

        if self.custom_connection_uri and self.current_db_id == db_id:
            return {
                "id": self.current_db_id,
                "name": self.current_db_name or self.current_db_id,
                "connection": self.custom_connection_uri
            }

        return None


    def set_database(self, db_id: str):
        db_config = self.get_database_config(db_id)
        if not db_config:
            raise ValueError(f"Database {db_id} not found in configured database folders or metadata database.")

        if db_config.get("connection") not in ["custom", None] and not db_config["connection"].startswith("sqlite"):
            self.custom_connection_uri = db_config["connection"]
        else:
            self.custom_connection_uri = None



        self.current_db_id = db_id
        self.current_db_name = db_config["name"]
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
        Scans DATABASE_FOLDER, configured DB directories, and registered metadata databases.
        """
        search_dirs = [self.db_folder]
        try:
            from services.metadata_service import metadata_service
            for d in metadata_service.list_db_directories():
                if d not in search_dirs and os.path.exists(d):
                    search_dirs.append(d)
        except Exception:
            pass

        seen_ids = set()
        db_list = []

        # 1. Local SQLite files
        for folder in search_dirs:
            if not os.path.exists(folder):
                continue
            files = [f for f in os.listdir(folder) if f.endswith(".db")]
            for f in sorted(files):
                if f not in seen_ids:
                    seen_ids.add(f)
                    db_list.append({"id": f, "name": f, "type": "sqlite"})

        # 2. Persisted Remote / Custom RDBMS entries from HadilDatabase metadata table
        try:
            from services.metadata_service import metadata_service
            registered = metadata_service.list_registered_databases()
            for r in registered:
                r_id = r["id"]
                if r_id not in seen_ids:
                    seen_ids.add(r_id)
                    db_list.append({
                        "id": r_id,
                        "name": r["name"],
                        "type": r.get("database_type", "custom")
                    })
        except Exception as e:
            logger.warning(f"Could not load registered databases from metadata: {e}")

        return sorted(db_list, key=lambda x: x["name"])

db_manager = DatabaseManager()


