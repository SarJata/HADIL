import os
import datetime
import hashlib
import json
import secrets
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, text

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

MetadataBase = declarative_base()

# Account / organization lifecycle (independent of RBAC roles)
STATUS_PENDING = "PENDING"
STATUS_ACTIVE = "ACTIVE"
STATUS_SUSPENDED = "SUSPENDED"
STATUS_REJECTED = "REJECTED"

ORG_ROLE_SUADMIN = "SUADMIN"
PLATFORM_ROLE_MASTER_ADMIN = "MASTER_ADMIN"
DB_ROLES = ("ADMIN", "EDITOR", "VIEWER")


class HadilOrganization(MetadataBase):
    """Customer tenant. Internal id is the security boundary; slug is the login suffix."""
    __tablename__ = "hadil_organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, nullable=False, default=STATUS_PENDING)
    # Cloud: organization selects a HADIL-allowed provider only (no model, no API key).
    ai_provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    users = relationship("HadilUser", back_populates="organization")
    databases = relationship("HadilDatabase", back_populates="organization")


class HadilDatabase(MetadataBase):
    __tablename__ = "hadil_databases"

    id = Column(String, primary_key=True, index=True) # e.g. "sales.db", "custom_db_1"
    name = Column(String, nullable=False)
    database_type = Column(String, nullable=False, default="sqlite") # e.g. "sqlite", "postgresql", "mysql"
    connection_uri_hash = Column(String, nullable=True) # Hash/reference if needed, avoid storing plaintext
    connection_uri_encrypted = Column(Text, nullable=True) # Encrypted connection string for remote RDBMS persistence
    status = Column(String, default="active")
    organization_id = Column(Integer, ForeignKey("hadil_organizations.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    organization = relationship("HadilOrganization", back_populates="databases")


    roles = relationship("HadilUserDatabaseRole", back_populates="database", cascade="all, delete-orphan")
    faqs = relationship("HadilDatabaseFAQ", back_populates="database", cascade="all, delete-orphan")
    schema_snapshots = relationship("HadilSchemaSnapshot", back_populates="database", cascade="all, delete-orphan")
    query_histories = relationship("HadilQueryHistoryMeta", back_populates="database", cascade="all, delete-orphan")
    pinned_widgets = relationship("HadilPinnedWidget", back_populates="database", cascade="all, delete-orphan")


class HadilUser(MetadataBase):
    __tablename__ = "hadil_users"

    id = Column(Integer, primary_key=True, index=True)
    # Login identifier: platform MASTER_ADMIN uses a bare username; org users use "user@slug".
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("hadil_organizations.id"), nullable=True, index=True)
    account_status = Column(String, nullable=False, default=STATUS_ACTIVE)
    organization_role = Column(String, nullable=True)  # SUADMIN inside an organization; never MASTER_ADMIN
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    organization = relationship("HadilOrganization", back_populates="users")
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


class HadilPlatformAIProvider(MetadataBase):
    """Platform-level AI provider policy. No API keys are stored here."""
    __tablename__ = "hadil_platform_ai_providers"

    provider_type = Column(String, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=True)
    model = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


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


def normalize_metadata_database_url(url: str) -> str:
    """Accept postgres://, postgresql://, and postgresql+psycopg2:// forms."""
    cleaned = (url or "").strip()
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg2://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg2://" + cleaned[len("postgresql://"):]
    return cleaned


class MetadataDatabaseManager:
    """
    Manages the standalone HADIL Metadata Database.

    Desktop default: local SQLite file (hadil_metadata.db).
    Cloud: PostgreSQL/Supabase via HADIL_METADATA_DATABASE_URL.
    """
    def __init__(self, db_path: str = "./hadil_metadata.db", database_url: str = None):
        self.db_path = db_path
        self.database_url = normalize_metadata_database_url(database_url) if database_url else None
        self.engine = self._create_engine()
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.init_db()

    def _create_engine(self):
        if self.database_url:
            pool_mode = (os.getenv("HADIL_METADATA_POOL_MODE") or "default").strip().lower()
            engine_kwargs = {"pool_pre_ping": True}
            if pool_mode in ("null", "none", "disabled"):
                from sqlalchemy.pool import NullPool
                engine_kwargs["poolclass"] = NullPool
            else:
                engine_kwargs["pool_size"] = int(os.getenv("HADIL_METADATA_POOL_SIZE", "5"))
                engine_kwargs["max_overflow"] = int(os.getenv("HADIL_METADATA_MAX_OVERFLOW", "5"))
            return create_engine(self.database_url, **engine_kwargs)
        return create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )

    def init_db(self):
        MetadataBase.metadata.create_all(bind=self.engine)
        self._ensure_column("hadil_databases", "connection_uri_encrypted", "TEXT")
        self._ensure_column("hadil_databases", "organization_id", "INTEGER")
        self._ensure_column("hadil_users", "organization_id", "INTEGER")
        self._ensure_column("hadil_users", "account_status", "VARCHAR")
        self._ensure_column("hadil_users", "organization_role", "VARCHAR")
        self._ensure_column("hadil_organizations", "ai_provider", "VARCHAR")
        self._backfill_account_status()

    def _backfill_account_status(self):
        """Existing users remain ACTIVE; never invent organizations for legacy rows."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(
                    "UPDATE hadil_users SET account_status = 'ACTIVE' "
                    "WHERE account_status IS NULL OR account_status = ''"
                ))
                conn.commit()
        except Exception:
            pass

    def _ensure_column(self, table_name: str, column_name: str, column_type: str):
        """Dialect-safe additive migration used by both SQLite and PostgreSQL."""
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(self.engine)
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            if column_name in existing:
                return
            with self.engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                conn.commit()
        except Exception:
            pass

    def is_healthy(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @property
    def dialect_name(self) -> str:
        return getattr(self.engine.dialect, "name", "sqlite")

    def get_session(self) -> Session:
        return self._SessionLocal()

from utils.path_resolver import resolve_user_data_resource

def _build_default_metadata_manager() -> MetadataDatabaseManager:
    database_url = os.getenv("HADIL_METADATA_DATABASE_URL")
    if database_url:
        return MetadataDatabaseManager(database_url=database_url)
    metadata_db_env = os.getenv("HADIL_METADATA_DB")
    if metadata_db_env:
        metadata_db_path = os.path.abspath(metadata_db_env)
    else:
        metadata_db_path = resolve_user_data_resource("hadil_metadata.db")
    return MetadataDatabaseManager(db_path=metadata_db_path)

metadata_manager = _build_default_metadata_manager()


def get_metadata_db():
    db = metadata_manager._SessionLocal()
    try:
        yield db
    finally:
        db.close()
