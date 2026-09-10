import os
import logging
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from database.metadata_db import (
    metadata_manager,
    HadilDatabase,
    HadilUser,
    HadilUserDatabaseRole,
    HadilSystemRole,
    HadilDatabaseFAQ,
    HadilSchemaSnapshot,
    HadilQueryHistoryMeta,
    HadilPinnedWidget,
    HadilLLMConfig,
    HadilDBDirectory,
    HadilPolicyDocument,
    hash_password
)

from services.secret_service import encrypt_secret, decrypt_secret
from utils.path_resolver import get_default_database_folder

logger = logging.getLogger(__name__)

class MetadataService:
    """
    Service layer providing CRUD and helper methods for HADIL Metadata Database entities.
    Enforces RBAC and database scoping.
    """

    # --- Database Registration & Scoping ---
    @staticmethod
    def register_or_update_database(
        db_id: str,
        name: str,
        database_type: str = "sqlite",
        connection_uri: Optional[str] = None,
        status: str = "active"
    ) -> HadilDatabase:
        db: Session = metadata_manager.get_session()
        try:
            uri_hash = hashlib.sha256(connection_uri.encode('utf-8')).hexdigest() if connection_uri else None
            uri_encrypted = encrypt_secret(connection_uri) if connection_uri else None
            db_record = db.query(HadilDatabase).filter(HadilDatabase.id == db_id).first()
            if not db_record:
                db_record = HadilDatabase(
                    id=db_id,
                    name=name,
                    database_type=database_type,
                    connection_uri_hash=uri_hash,
                    connection_uri_encrypted=uri_encrypted,
                    status=status
                )
                db.add(db_record)
            else:
                db_record.name = name
                db_record.database_type = database_type
                if uri_hash:
                    db_record.connection_uri_hash = uri_hash
                    db_record.connection_uri_encrypted = uri_encrypted
                db_record.status = status
            db.commit()
            db.refresh(db_record)
            return db_record
        finally:
            db.close()

    @staticmethod
    def register_sqlite_file_database(
        file_path: str,
        display_name: str,
        is_managed_upload: bool = False
    ) -> Dict[str, Any]:
        """
        Validates, introspects, and registers a local SQLite database file in HADIL metadata.
        Prevents path traversal, checks SQLite file header, tests connectivity, and prevents overwriting.
        """
        import uuid
        from sqlalchemy import create_engine, text

        abs_path = os.path.abspath(os.path.normpath(file_path))
        if not os.path.exists(abs_path):
            raise ValueError("Target database file does not exist on server.")
        if not os.path.isfile(abs_path):
            raise ValueError("Target path is not a file.")

        # Verify SQLite Magic Header (16 bytes: b"SQLite format 3\x00")
        try:
            with open(abs_path, "rb") as f:
                header = f.read(16)
                if header != b"SQLite format 3\x00":
                    raise ValueError("File is not a valid SQLite format 3 database.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            raise ValueError(f"Cannot read file header: {e}")

        # Verify database can be opened by SQLAlchemy
        connection_uri = f"sqlite:///{abs_path}"
        try:
            test_engine = create_engine(connection_uri, connect_args={"check_same_thread": False})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_engine.dispose()
        except Exception as e:
            raise ValueError(f"SQLite file is corrupt or cannot be opened: {e}")

        clean_name = display_name.strip() if display_name and display_name.strip() else os.path.basename(abs_path)
        
        # Generate safe database ID using the actual target file basename
        base_id = os.path.basename(abs_path)
        db_id = base_id if base_id.endswith(".db") else f"{base_id}.db"

        # Check existing registration

        db: Session = metadata_manager.get_session()
        try:
            existing = db.query(HadilDatabase).filter(HadilDatabase.id == db_id).first()
            if existing and not is_managed_upload:
                # Update display name if already registered
                existing.name = clean_name
                db.commit()
                return {
                    "id": existing.id,
                    "name": existing.name,
                    "database_type": existing.database_type,
                    "storage_mode": "MANAGED_UPLOAD" if is_managed_upload else "EXISTING_FILE",
                    "status": "registered"
                }

            record = HadilDatabase(
                id=db_id,
                name=clean_name,
                database_type="sqlite",
                connection_uri_hash=hashlib.sha256(connection_uri.encode('utf-8')).hexdigest(),
                connection_uri_encrypted=encrypt_secret(connection_uri),
                status="active"
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return {
                "id": record.id,
                "name": record.name,
                "database_type": record.database_type,
                "storage_mode": "MANAGED_UPLOAD" if is_managed_upload else "EXISTING_FILE",
                "status": "registered"
            }
        finally:
            db.close()


    @staticmethod
    def get_decrypted_connection_uri(db_id: str) -> Optional[str]:
        db: Session = metadata_manager.get_session()
        try:
            db_record = db.query(HadilDatabase).filter(HadilDatabase.id == db_id).first()
            if db_record and db_record.connection_uri_encrypted:
                return decrypt_secret(db_record.connection_uri_encrypted)
            return None
        finally:
            db.close()


    @staticmethod
    def get_database(db_id: str) -> Optional[HadilDatabase]:
        db: Session = metadata_manager.get_session()
        try:
            return db.query(HadilDatabase).filter(HadilDatabase.id == db_id).first()
        finally:
            db.close()

    @staticmethod
    def list_registered_databases() -> List[Dict[str, Any]]:
        db: Session = metadata_manager.get_session()
        try:
            records = db.query(HadilDatabase).all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "database_type": r.database_type,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in records
            ]
        finally:
            db.close()

    # --- Users & Password Management ---
    @staticmethod
    def create_user(username: str, password_raw: str) -> HadilUser:
        db: Session = metadata_manager.get_session()
        try:
            existing = db.query(HadilUser).filter(HadilUser.username == username).first()
            if existing:
                raise ValueError(f"User '{username}' already exists.")
            
            hashed = hash_password(password_raw)
            user = HadilUser(username=username, password_hash=hashed)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()

    @staticmethod
    def get_user_by_username(username: str) -> Optional[HadilUser]:
        db: Session = metadata_manager.get_session()
        try:
            return db.query(HadilUser).filter(HadilUser.username == username).first()
        finally:
            db.close()

    @staticmethod
    def get_setup_status(db_session: Optional[Session] = None) -> Dict[str, bool]:
        """
        Returns setup_required status based on persistent HadilUser count in metadata DB.
        """
        close_session = False
        if db_session is None:
            db_session = metadata_manager.get_session()
            close_session = True
        try:
            count = db_session.query(HadilUser).count()
            return {"setup_required": (count == 0)}
        finally:
            if close_session:
                db_session.close()

    @staticmethod
    def create_first_admin(username: str, password_raw: str, db_session: Optional[Session] = None) -> HadilUser:
        """
        Atomically creates the initial ADMIN user when 0 users exist.
        If at least one user already exists, raises ValueError("Initial setup has already been completed.").
        """
        close_session = False
        if db_session is None:
            db_session = metadata_manager.get_session()
            close_session = True
        try:
            # Check within transaction
            user_count = db_session.query(HadilUser).count()
            if user_count > 0:
                raise ValueError("Initial setup has already been completed.")

            clean_user = username.strip()
            existing_user = db_session.query(HadilUser).filter(HadilUser.username == clean_user).first()
            if existing_user:
                raise ValueError("Initial setup has already been completed.")

            # Discover registered/available databases

            all_dbs = db_session.query(HadilDatabase).all()
            db_ids = [d.id for d in all_dbs]
            db_folder = get_default_database_folder()
            if os.path.exists(db_folder):
                for f in os.listdir(db_folder):
                    if f.endswith(".db") and f not in db_ids:
                        new_db = HadilDatabase(id=f, name=f, database_type="sqlite")
                        db_session.add(new_db)
                        db_ids.append(f)
            if not db_ids:
                db_ids = ["default_db"]

            hashed = hash_password(password_raw)
            user = HadilUser(username=username.strip(), password_hash=hashed)
            db_session.add(user)
            db_session.flush()

            # Assign MASTER_ADMIN system role to initial setup-created administrator
            sys_role = HadilSystemRole(slot=1, user_id=user.id, role="MASTER_ADMIN")
            db_session.add(sys_role)

            for db_id in db_ids:
                role_rec = HadilUserDatabaseRole(
                    user_id=user.id,
                    database_id=db_id,
                    role="ADMIN"
                )
                db_session.add(role_rec)

            db_session.commit()
            db_session.refresh(user)
            return user
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            if close_session:
                db_session.close()

    @staticmethod
    def list_users() -> List[Dict[str, Any]]:
        db: Session = metadata_manager.get_session()
        try:
            users = db.query(HadilUser).all()
            result = []
            for u in users:
                roles = [
                    {"database_id": r.database_id, "role": r.role}
                    for r in u.roles
                ]
                result.append({
                    "id": u.id,
                    "username": u.username,
                    "roles": roles,
                    "created_at": u.created_at.isoformat() if u.created_at else None
                })
            return result
        finally:
            db.close()

    @staticmethod
    def reset_and_seed_per_db_admins(default_password: str = "password123") -> List[Dict[str, Any]]:
        """
        Deletes all existing users and roles from hadil_metadata.db,
        discovers all registered/available databases, and creates a separate
        dedicated ADMIN user for each database, plus a master admin user.
        """
        db: Session = metadata_manager.get_session()
        try:
            # Delete all existing user roles and users
            from database.metadata_db import HadilSystemRole
            db.query(HadilSystemRole).delete()
            db.query(HadilUserDatabaseRole).delete()
            db.query(HadilUser).delete()
            db.commit()

            # Discover databases in HadilDatabase table
            all_dbs = db.query(HadilDatabase).all()
            db_ids = [d.id for d in all_dbs]

            # Also discover local database files in configured db folder
            db_folder = get_default_database_folder()
            if os.path.exists(db_folder):
                for f in os.listdir(db_folder):
                    if f.endswith(".db") and f not in db_ids:
                        new_db = HadilDatabase(id=f, name=f, database_type="sqlite")
                        db.add(new_db)
                        db_ids.append(f)
                db.commit()

            if not db_ids:
                db_ids = ["default_db"]

            created_users = []

            # 1. Master Super Admin user
            master_user = HadilUser(
                username="admin",
                password_hash=hash_password(default_password)
            )
            db.add(master_user)
            db.commit()
            db.refresh(master_user)

            # Assign system role MASTER_ADMIN
            sys_role = HadilSystemRole(
                slot=1,
                user_id=master_user.id,
                role="MASTER_ADMIN"
            )
            db.add(sys_role)

            master_roles = []
            for db_id in db_ids:
                role_rec = HadilUserDatabaseRole(
                    user_id=master_user.id,
                    database_id=db_id,
                    role="ADMIN"
                )
                db.add(role_rec)
                master_roles.append({"database_id": db_id, "role": "ADMIN"})
            db.commit()



            created_users.append({
                "id": master_user.id,
                "username": master_user.username,
                "password": default_password,
                "roles": master_roles
            })

            # 2. Separate Admin User for each Database
            for db_id in db_ids:
                clean_name = db_id.replace(".db", "").replace(" ", "_").lower()
                username = f"admin_{clean_name}"
                
                if username == "admin":
                    username = f"admin_{clean_name}_db"

                db_admin_user = HadilUser(
                    username=username,
                    password_hash=hash_password(default_password)
                )
                db.add(db_admin_user)
                db.commit()
                db.refresh(db_admin_user)

                # Assign ADMIN role ONLY to this specific database
                role_rec = HadilUserDatabaseRole(
                    user_id=db_admin_user.id,
                    database_id=db_id,
                    role="ADMIN"
                )
                db.add(role_rec)
                db.commit()

                created_users.append({
                    "id": db_admin_user.id,
                    "username": username,
                    "password": default_password,
                    "roles": [{"database_id": db_id, "role": "ADMIN"}]
                })

            return created_users
        finally:
            db.close()


    # --- Scoped RBAC Roles ---
    @staticmethod
    def assign_user_role(user_id: int, database_id: str, role: str) -> HadilUserDatabaseRole:
        valid_roles = ["ADMIN", "EDITOR", "VIEWER"]
        role_upper = role.upper()
        if role_upper not in valid_roles:
            raise ValueError(f"Invalid role '{role}'. Must be one of {valid_roles}")

        db: Session = metadata_manager.get_session()
        try:
            existing = db.query(HadilUserDatabaseRole).filter(
                HadilUserDatabaseRole.user_id == user_id,
                HadilUserDatabaseRole.database_id == database_id
            ).first()

            if existing:
                existing.role = role_upper
                db.commit()
                db.refresh(existing)
                return existing
            else:
                user_role = HadilUserDatabaseRole(
                    user_id=user_id,
                    database_id=database_id,
                    role=role_upper
                )
                db.add(user_role)
                db.commit()
                db.refresh(user_role)
                return user_role
        finally:
            db.close()

    @staticmethod
    def get_master_admin(db_session: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """
        Returns Master Administrator details if one exists, otherwise None.
        """
        close_session = False
        if db_session is None:
            db_session = metadata_manager.get_session()
            close_session = True
        try:
            sys_role = db_session.query(HadilSystemRole).filter(HadilSystemRole.role == "MASTER_ADMIN").first()
            if not sys_role:
                return None
            user = db_session.query(HadilUser).filter(HadilUser.id == sys_role.user_id).first()
            if not user:
                return None
            return {
                "user_id": user.id,
                "username": user.username,
                "created_at": sys_role.created_at.isoformat() if sys_role.created_at else None
            }
        finally:
            if close_session:
                db_session.close()

    @staticmethod
    def create_master_admin(username: str, password_raw: str, db_session: Optional[Session] = None) -> HadilUser:
        """
        Atomically creates the single MASTER_ADMIN user.
        Strictly enforces that MAXIMUM 1 MASTER_ADMIN can exist in the system.
        If a MASTER_ADMIN already exists, raises ValueError("A Master Administrator already exists. Master Administrator creation is unavailable.").
        """
        close_session = False
        if db_session is None:
            db_session = metadata_manager.get_session()
            close_session = True
        try:
            # 1. Check if MASTER_ADMIN already exists
            existing_master = db_session.query(HadilSystemRole).filter(HadilSystemRole.role == "MASTER_ADMIN").first()
            if existing_master:
                raise ValueError("A Master Administrator already exists. Master Administrator creation is unavailable.")

            clean_username = username.strip()
            if not clean_username:
                raise ValueError("Username cannot be empty.")
            if not password_raw or len(password_raw) == 0:
                raise ValueError("Password cannot be empty.")

            # Check if username is already taken by another user
            existing_user = db_session.query(HadilUser).filter(HadilUser.username == clean_username).first()
            if existing_user:
                raise ValueError(f"User '{clean_username}' already exists.")

            # 2. Hash password using standard HADIL hash_password helper
            hashed = hash_password(password_raw)
            user = HadilUser(username=clean_username, password_hash=hashed)
            db_session.add(user)
            db_session.flush()

            # 3. Insert into HadilSystemRole with fixed slot=1 (Enforces exactly-one uniqueness at DB level)
            sys_role = HadilSystemRole(slot=1, user_id=user.id, role="MASTER_ADMIN")
            db_session.add(sys_role)

            # 4. Assign ADMIN role across all registered databases for seamless scoping
            all_dbs = db_session.query(HadilDatabase).all()
            db_ids = [d.id for d in all_dbs]
            db_folder = get_default_database_folder()
            if os.path.exists(db_folder):
                for f in os.listdir(db_folder):
                    if f.endswith(".db") and f not in db_ids:
                        new_db = HadilDatabase(id=f, name=f, database_type="sqlite")
                        db_session.add(new_db)
                        db_ids.append(f)

            for db_id in db_ids:
                role_rec = HadilUserDatabaseRole(
                    user_id=user.id,
                    database_id=db_id,
                    role="ADMIN"
                )
                db_session.add(role_rec)

            db_session.commit()
            db_session.refresh(user)
            return user
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            if close_session:
                db_session.close()

    @staticmethod
    def get_user_role_for_database(user_id: int, database_id: str) -> Optional[str]:
        db: Session = metadata_manager.get_session()
        try:
            # Check if user is MASTER_ADMIN
            master_rec = db.query(HadilSystemRole).filter(
                HadilSystemRole.user_id == user_id,
                HadilSystemRole.role == "MASTER_ADMIN"
            ).first()
            if master_rec:
                return "MASTER_ADMIN"

            record = db.query(HadilUserDatabaseRole).filter(
                HadilUserDatabaseRole.user_id == user_id,
                HadilUserDatabaseRole.database_id == database_id
            ).first()
            return record.role if record else None
        finally:
            db.close()

    # RBAC Permission Verification Helper
    @staticmethod
    def check_permission(user_id: int, database_id: str, action: str) -> bool:
        """
        Enforces Database-Scoped RBAC Rules:
        MASTER_ADMIN: All administrative & operation permissions across all databases
        ADMIN: READ, ADD, UPDATE, DELETE, MANAGE_USERS
        EDITOR: READ, ADD, UPDATE
        VIEWER: READ
        """
        role = MetadataService.get_user_role_for_database(user_id, database_id)
        if not role:
            return False
        
        action_upper = action.upper()
        if role in ["MASTER_ADMIN", "ADMIN"]:
            return action_upper in ["READ", "ADD", "ADD_TABLE", "UPDATE", "DELETE", "MANAGE_USERS"]
        elif role == "EDITOR":
            return action_upper in ["READ", "ADD", "ADD_TABLE", "UPDATE"]
        elif role == "VIEWER":
            return action_upper in ["READ"]
        return False


    # --- Scoped FAQs ---
    @staticmethod
    def add_faq(database_id: str, question: str, answer: str) -> HadilDatabaseFAQ:
        db: Session = metadata_manager.get_session()
        try:
            faq = HadilDatabaseFAQ(database_id=database_id, question=question, answer=answer)
            db.add(faq)
            db.commit()
            db.refresh(faq)
            return faq
        finally:
            db.close()

    @staticmethod
    def get_faqs_for_database(database_id: str) -> List[HadilDatabaseFAQ]:
        db: Session = metadata_manager.get_session()
        try:
            return db.query(HadilDatabaseFAQ).filter(HadilDatabaseFAQ.database_id == database_id).all()
        finally:
            db.close()

    # --- Scoped Schema Snapshots ---
    @staticmethod
    def save_schema_snapshot(database_id: str, schema_json_str: str) -> HadilSchemaSnapshot:
        db: Session = metadata_manager.get_session()
        try:
            snapshot = HadilSchemaSnapshot(database_id=database_id, schema_data=schema_json_str)
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
            return snapshot
        finally:
            db.close()

    @staticmethod
    def get_latest_schema_snapshot(database_id: str) -> Optional[HadilSchemaSnapshot]:
        db: Session = metadata_manager.get_session()
        try:
            return db.query(HadilSchemaSnapshot).filter(
                HadilSchemaSnapshot.database_id == database_id
            ).order_by(HadilSchemaSnapshot.created_at.desc()).first()
        finally:
            db.close()

    # --- Scoped Query History ---
    @staticmethod
    def log_query_history(database_id: str, query: str, user_id: Optional[int] = None, operation: str = "SELECT", status: str = "SUCCESS") -> HadilQueryHistoryMeta:
        db: Session = metadata_manager.get_session()
        try:
            hist = HadilQueryHistoryMeta(
                user_id=user_id,
                database_id=database_id,
                query=query,
                operation=operation,
                status=status
            )
            db.add(hist)
            db.commit()
            db.refresh(hist)
            return hist
        finally:
            db.close()

    # --- Scoped Pinned Widgets ---
    @staticmethod
    def add_pinned_widget(database_id: str, widget_config_str: str, user_id: Optional[int] = None) -> HadilPinnedWidget:
        db: Session = metadata_manager.get_session()
        try:
            widget = HadilPinnedWidget(
                user_id=user_id,
                database_id=database_id,
                widget_configuration=widget_config_str
            )
            db.add(widget)
            db.commit()
            db.refresh(widget)
            return widget
        finally:
            db.close()

    @staticmethod
    def get_pinned_widgets_for_database(database_id: str, user_id: Optional[int] = None) -> List[HadilPinnedWidget]:
        db: Session = metadata_manager.get_session()
        try:
            q = db.query(HadilPinnedWidget).filter(HadilPinnedWidget.database_id == database_id)
            if user_id:
                q = q.filter(HadilPinnedWidget.user_id == user_id)
            return q.all()
        finally:
            db.close()

    @staticmethod
    def get_llm_config(target: str) -> Dict[str, Any]:
        """
        Returns safe LLM provider configuration for UI/Admin without exposing raw API keys.
        """
        db: Session = metadata_manager.get_session()
        try:
            cfg = db.query(HadilLLMConfig).filter(HadilLLMConfig.target == target.lower()).first()
            if not cfg:
                return {
                    "target": target.lower(),
                    "provider_type": os.getenv("LLM_PROVIDER", "openai").lower(),
                    "endpoint": os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat") if os.getenv("LLM_PROVIDER") == "qwen" else None,
                    "model": os.getenv("QWEN_MODEL", "qwen2.5-coder:3b") if os.getenv("LLM_PROVIDER") == "qwen" else os.getenv("OPENAI_MODEL", "gpt-4o"),
                    "api_key_configured": bool(os.getenv("OPENAI_API_KEY"))
                }
            return {
                "target": cfg.target,
                "provider_type": cfg.provider_type,
                "endpoint": cfg.endpoint,
                "model": cfg.model,
                "api_key_configured": bool(cfg.api_key_encrypted)
            }
        finally:
            db.close()

    @staticmethod
    def get_llm_config_internal(target: str) -> Dict[str, Any]:
        """
        Returns raw configuration including decrypted API key for backend execution.
        Isolated per provider type to prevent cross-provider credential leakage.
        """
        db: Session = metadata_manager.get_session()
        try:
            cfg = db.query(HadilLLMConfig).filter(HadilLLMConfig.target == target.lower()).first()
            if not cfg:
                p_type = os.getenv("LLM_PROVIDER", "openai").lower().strip()
                env_key = None
                if p_type in ["gemini", "google"]: env_key = os.getenv("GEMINI_API_KEY")
                elif p_type == "sarvam": env_key = os.getenv("SARVAM_API_KEY")
                elif p_type == "openai": env_key = os.getenv("OPENAI_API_KEY")
                elif p_type in ["claude", "anthropic"]: env_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

                return {
                    "target": target.lower(),
                    "provider_type": p_type,
                    "endpoint": os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat") if p_type in ["qwen", "ollama"] else None,
                    "model": os.getenv("QWEN_MODEL", "qwen2.5-coder:3b") if p_type in ["qwen", "ollama"] else os.getenv("OPENAI_MODEL", "gpt-4o"),
                    "api_key": env_key
                }

            p_type = cfg.provider_type.lower().strip() if cfg.provider_type else "openai"
            api_key = decrypt_secret(cfg.api_key_encrypted) if cfg.api_key_encrypted else None

            # Fallback to provider-specific env var if DB key is missing
            if not api_key:
                if p_type in ["gemini", "google"]:
                    api_key = os.getenv("GEMINI_API_KEY")
                elif p_type == "sarvam":
                    api_key = os.getenv("SARVAM_API_KEY")
                elif p_type == "openai":
                    api_key = os.getenv("OPENAI_API_KEY")
                elif p_type in ["claude", "anthropic"]:
                    api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

            return {
                "target": cfg.target,
                "provider_type": p_type,
                "endpoint": cfg.endpoint if p_type in ["custom", "ollama", "qwen"] else None,
                "model": cfg.model,
                "api_key": api_key
            }
        finally:
            db.close()

    @staticmethod
    def set_llm_config(
        target: str,
        provider_type: str,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Saves or updates LLM provider configuration for a target ('generator' or 'verifier').
        Ensures strict endpoint and credential isolation when provider_type changes.
        """
        target_lower = target.lower().strip()
        provider_clean = provider_type.lower().strip()
        db: Session = metadata_manager.get_session()
        try:
            cfg = db.query(HadilLLMConfig).filter(HadilLLMConfig.target == target_lower).first()
            clean_endpoint = endpoint.strip() if (endpoint and endpoint.strip() and provider_clean in ["custom", "ollama", "qwen"]) else None

            if not cfg:
                cfg = HadilLLMConfig(
                    target=target_lower,
                    provider_type=provider_clean,
                    endpoint=clean_endpoint,
                    model=model.strip() if model else None,
                    api_key_encrypted=encrypt_secret(api_key.strip()) if api_key and api_key.strip() and api_key != "••••••••" else None
                )
                db.add(cfg)
            else:
                provider_changed = (cfg.provider_type != provider_clean)
                cfg.provider_type = provider_clean
                cfg.endpoint = clean_endpoint

                if model is not None:
                    cfg.model = model.strip() if model else None

                if api_key and api_key.strip() and api_key != "••••••••":
                    cfg.api_key_encrypted = encrypt_secret(api_key.strip())
                elif provider_changed:
                    # Purge old provider's encrypted secret on provider change if new key not provided
                    cfg.api_key_encrypted = None

            db.commit()
            db.refresh(cfg)
            return {
                "target": cfg.target,
                "provider_type": cfg.provider_type,
                "endpoint": cfg.endpoint,
                "model": cfg.model,
                "api_key_configured": bool(cfg.api_key_encrypted)
            }
        finally:
            db.close()

    # --- Database Directory Configuration Management ---
    @staticmethod
    def list_db_directories() -> List[str]:
        db: Session = metadata_manager.get_session()
        try:
            records = db.query(HadilDBDirectory).all()
            dirs = [r.path for r in records]
            # Ensure default runtime database folder is included if configured
            default_dir = os.path.abspath(get_default_database_folder())
            if default_dir not in dirs and os.path.exists(default_dir):
                dirs.insert(0, default_dir)
            return dirs
        finally:
            db.close()

    @staticmethod
    def add_db_directory(path: str) -> str:
        norm_path = os.path.abspath(os.path.normpath(path.strip()))
        if not os.path.exists(norm_path) or not os.path.isdir(norm_path):
            raise ValueError(f"Directory path '{norm_path}' does not exist or is not a directory.")

        db: Session = metadata_manager.get_session()
        try:
            existing = db.query(HadilDBDirectory).filter(HadilDBDirectory.path == norm_path).first()
            if existing:
                raise ValueError(f"Directory '{norm_path}' is already configured.")
            record = HadilDBDirectory(path=norm_path)
            db.add(record)
            db.commit()
            return norm_path
        finally:
            db.close()

    @staticmethod
    def remove_db_directory(path: str) -> bool:
        norm_path = os.path.abspath(os.path.normpath(path.strip()))
        db: Session = metadata_manager.get_session()
        try:
            record = db.query(HadilDBDirectory).filter(HadilDBDirectory.path == norm_path).first()
            if record:
                db.delete(record)
                db.commit()
                return True
            return False
        finally:
            db.close()


    # --- Policy Documents CRUD ---
    @staticmethod
    def create_policy_document(
        doc_id: str,
        filename: str,
        doc_type: str,
        scope: str,
        uploaded_by_user_id: int,
        file_path: str,
        embedding_model: str = "all-MiniLM-L6-v2"
    ) -> HadilPolicyDocument:
        db: Session = metadata_manager.get_session()
        try:
            doc = HadilPolicyDocument(
                id=doc_id,
                filename=filename,
                doc_type=doc_type,
                scope=scope,
                uploaded_by_user_id=uploaded_by_user_id,
                file_path=file_path,
                indexing_status="PENDING",
                chunk_count=0,
                embedding_model=embedding_model
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return doc
        finally:
            db.close()

    @staticmethod
    def update_policy_document_status(
        doc_id: str,
        status: str,
        chunk_count: int = 0
    ) -> Optional[HadilPolicyDocument]:
        db: Session = metadata_manager.get_session()
        try:
            doc = db.query(HadilPolicyDocument).filter(HadilPolicyDocument.id == doc_id).first()
            if doc:
                doc.indexing_status = status
                doc.chunk_count = chunk_count
                db.commit()
                db.refresh(doc)
            return doc
        finally:
            db.close()

    @staticmethod
    def list_policy_documents(scope: Optional[str] = None) -> List[Dict[str, Any]]:
        db: Session = metadata_manager.get_session()
        try:
            q = db.query(HadilPolicyDocument)
            if scope:
                q = q.filter(HadilPolicyDocument.scope == scope)
            records = q.order_by(HadilPolicyDocument.upload_timestamp.desc()).all()
            return [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "doc_type": r.doc_type,
                    "scope": r.scope,
                    "upload_timestamp": r.upload_timestamp.isoformat() if r.upload_timestamp else None,
                    "uploaded_by_user_id": r.uploaded_by_user_id,
                    "indexing_status": r.indexing_status,
                    "chunk_count": r.chunk_count,
                    "embedding_model": r.embedding_model,
                    "file_path": r.file_path
                }
                for r in records
            ]
        finally:
            db.close()

    @staticmethod
    def get_policy_document(doc_id: str) -> Optional[HadilPolicyDocument]:
        db: Session = metadata_manager.get_session()
        try:
            return db.query(HadilPolicyDocument).filter(HadilPolicyDocument.id == doc_id).first()
        finally:
            db.close()

    @staticmethod
    def delete_policy_document(doc_id: str) -> bool:
        db: Session = metadata_manager.get_session()
        try:
            doc = db.query(HadilPolicyDocument).filter(HadilPolicyDocument.id == doc_id).first()
            if doc:
                db.delete(doc)
                db.commit()
                return True
            return False
        finally:
            db.close()

metadata_service = MetadataService()


