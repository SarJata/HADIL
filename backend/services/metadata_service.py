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
    HadilDatabaseFAQ,
    HadilSchemaSnapshot,
    HadilQueryHistoryMeta,
    HadilPinnedWidget,
    hash_password
)

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
            db_record = db.query(HadilDatabase).filter(HadilDatabase.id == db_id).first()
            if not db_record:
                db_record = HadilDatabase(
                    id=db_id,
                    name=name,
                    database_type=database_type,
                    connection_uri_hash=uri_hash,
                    status=status
                )
                db.add(db_record)
            else:
                db_record.name = name
                db_record.database_type = database_type
                if uri_hash:
                    db_record.connection_uri_hash = uri_hash
                db_record.status = status
            db.commit()
            db.refresh(db_record)
            return db_record
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
            db.query(HadilUserDatabaseRole).delete()
            db.query(HadilUser).delete()
            db.commit()

            # Discover databases in HadilDatabase table
            all_dbs = db.query(HadilDatabase).all()
            db_ids = [d.id for d in all_dbs]

            # Also discover local database files in ./databases
            db_folder = os.getenv("DATABASE_FOLDER", "./databases")
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
    def get_user_role_for_database(user_id: int, database_id: str) -> Optional[str]:
        db: Session = metadata_manager.get_session()
        try:
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
        ADMIN: READ, ADD, UPDATE, DELETE, MANAGE_USERS
        EDITOR: READ, ADD, UPDATE
        VIEWER: READ
        """
        role = MetadataService.get_user_role_for_database(user_id, database_id)
        if not role:
            return False
        
        action_upper = action.upper()
        if role == "ADMIN":
            return action_upper in ["READ", "ADD", "UPDATE", "DELETE", "MANAGE_USERS"]
        elif role == "EDITOR":
            return action_upper in ["READ", "ADD", "UPDATE"]
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

metadata_service = MetadataService()
