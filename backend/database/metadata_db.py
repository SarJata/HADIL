import os
import datetime
import hashlib
import json
import secrets
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, text

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

MetadataBase = declarative_base()

class HadilDatabase(MetadataBase):
    __tablename__ = "hadil_databases"

    id = Column(String, primary_key=True, index=True) # e.g. "sales.db", "custom_db_1"
    name = Column(String, nullable=False)
    database_type = Column(String, nullable=False, default="sqlite") # e.g. "sqlite", "postgresql", "mysql"
    connection_uri_hash = Column(String, nullable=True) # Hash/reference if needed, avoid storing plaintext
    connection_uri_encrypted = Column(Text, nullable=True) # Encrypted connection string for remote RDBMS persistence
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


    roles = relationship("HadilUserDatabaseRole", back_populates="database", cascade="all, delete-orphan")
    faqs = relationship("HadilDatabaseFAQ", back_populates="database", cascade="all, delete-orphan")
    schema_snapshots = relationship("HadilSchemaSnapshot", back_populates="database", cascade="all, delete-orphan")
    query_histories = relationship("HadilQueryHistoryMeta", back_populates="database", cascade="all, delete-orphan")
    pinned_widgets = relationship("HadilPinnedWidget", back_populates="database", cascade="all, delete-orphan")


class HadilUser(MetadataBase):
    __tablename__ = "hadil_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    roles = relationship("HadilUserDatabaseRole", back_populates="user", cascade="all, delete-orphan")
    query_histories = relationship("HadilQueryHistoryMeta", back_populates="user", cascade="all, delete-orphan")
    pinned_widgets = relationship("HadilPinnedWidget", back_populates="user", cascade="all, delete-orphan")


class HadilUserDatabaseRole(MetadataBase):
    __tablename__ = "hadil_user_database_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("hadil_users.id"), nullable=False)
    database_id = Column(String, ForeignKey("hadil_databases.id"), nullable=False)
    role = Column(String, nullable=False) # "ADMIN", "EDITOR", "VIEWER"

    user = relationship("HadilUser", back_populates="roles")
    database = relationship("HadilDatabase", back_populates="roles")


class HadilSystemRole(MetadataBase):
    """
    Persists system-wide singleton roles.
    Enforces AT MOST ONE MASTER_ADMIN at the database level via fixed slot key/unique constraint.
    slot: Always 1 (only 1 row can ever exist with slot=1).
    """
    __tablename__ = "hadil_system_roles"

    slot = Column(Integer, primary_key=True, default=1)
    user_id = Column(Integer, ForeignKey("hadil_users.id"), nullable=False, unique=True)
    role = Column(String, nullable=False, default="MASTER_ADMIN")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("HadilUser")


class HadilDatabaseFAQ(MetadataBase):
    __tablename__ = "hadil_database_faqs"

    id = Column(Integer, primary_key=True, index=True)
    database_id = Column(String, ForeignKey("hadil_databases.id"), nullable=False)
    question = Column(String, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    database = relationship("HadilDatabase", back_populates="faqs")


class HadilSchemaSnapshot(MetadataBase):
    __tablename__ = "hadil_schema_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    database_id = Column(String, ForeignKey("hadil_databases.id"), nullable=False)
    schema_data = Column(Text, nullable=False) # JSON metadata string containing tables, columns, types, FKs, PKs
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    database = relationship("HadilDatabase", back_populates="schema_snapshots")


class HadilQueryHistoryMeta(MetadataBase):
    __tablename__ = "hadil_query_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("hadil_users.id"), nullable=True)
    database_id = Column(String, ForeignKey("hadil_databases.id"), nullable=False)
    query = Column(Text, nullable=False) # Natural or SQL query
    operation = Column(String, default="SELECT")
    status = Column(String, default="SUCCESS")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("HadilUser", back_populates="query_histories")
    database = relationship("HadilDatabase", back_populates="query_histories")


class HadilPinnedWidget(MetadataBase):
    __tablename__ = "hadil_pinned_widgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("hadil_users.id"), nullable=True)
    database_id = Column(String, ForeignKey("hadil_databases.id"), nullable=False)
    widget_configuration = Column(Text, nullable=False) # JSON configuration
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("HadilUser", back_populates="pinned_widgets")
    database = relationship("HadilDatabase", back_populates="pinned_widgets")


class HadilLLMConfig(MetadataBase):
    __tablename__ = "hadil_llm_config"

    id = Column(Integer, primary_key=True, index=True)
    target = Column(String, unique=True, index=True, nullable=False) # "generator" or "verifier"
    provider_type = Column(String, nullable=False, default="openai") # "openai", "ollama", "custom"
    endpoint = Column(String, nullable=True) # e.g. "https://ai.company.local/v1"
    model = Column(String, nullable=True) # e.g. "company-sql-model", "qwen2.5-coder:3b", "gpt-4o"
    api_key_encrypted = Column(String, nullable=True) # Encrypted secret string (never exposed raw via GET)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class HadilDBDirectory(MetadataBase):
    __tablename__ = "hadil_db_directories"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class HadilPolicyDocument(MetadataBase):

    __tablename__ = "hadil_policy_documents"

    id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    doc_type = Column(String, nullable=False) # "pdf", "txt", "docx"
    scope = Column(String, nullable=False, index=True) # "GLOBAL" or "DATABASE:<database_id>"
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    uploaded_by_user_id = Column(Integer, ForeignKey("hadil_users.id"), nullable=False)
    indexing_status = Column(String, nullable=False, default="PENDING") # "INDEXED", "FAILED", "PENDING"
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String, nullable=False, default="all-MiniLM-L6-v2")
    file_path = Column(String, nullable=False)

    uploaded_by = relationship("HadilUser")


# Password hashing helper using SHA-256 with salt (standard library fallback, upgradeable to Argon2/bcrypt)

def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    ).hex()
    return f"pbkdf2:sha256:100000${salt}${pw_hash}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        parts = hashed.split("$")
        if len(parts) != 3 or not parts[0].startswith("pbkdf2"):
            return False
        salt = parts[1]
        expected_hash = hash_password(password, salt)
        return secrets.compare_digest(expected_hash, hashed)
    except Exception:
        return False


class MetadataDatabaseManager:
    """
    Manages the standalone HADIL Metadata Database (hadil_metadata.db).
    """
    def __init__(self, db_path: str = "./hadil_metadata.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_db()

    def init_db(self):
        MetadataBase.metadata.create_all(bind=self.engine)
        # Migration: Ensure connection_uri_encrypted column exists on hadil_databases table
        try:
            with self.engine.connect() as conn:
                conn.execute(text("ALTER TABLE hadil_databases ADD COLUMN connection_uri_encrypted TEXT"))
                conn.commit()
        except Exception:
            pass


    def get_session(self) -> Session:
        return self._SessionLocal()

from utils.path_resolver import resolve_user_data_resource

metadata_db_env = os.getenv("HADIL_METADATA_DB")
if metadata_db_env:
    metadata_db_path = os.path.abspath(metadata_db_env)
else:
    metadata_db_path = resolve_user_data_resource("hadil_metadata.db")

metadata_manager = MetadataDatabaseManager(db_path=metadata_db_path)


def get_metadata_db():
    db = metadata_manager._SessionLocal()
    try:
        yield db
    finally:
        db.close()
