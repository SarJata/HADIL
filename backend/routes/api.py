import os
import uuid
import logging
import datetime
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text, Table, MetaData, Column, Integer, BigInteger, Float, Numeric, Boolean, String, Text, Date, DateTime, ForeignKeyConstraint, inspect
from pydantic import BaseModel
from typing import List, Optional, Dict, Any



from database.session import get_db, get_engine
from database.manager import db_manager
from database import models
from database.schema_extractor import get_table_schema, get_filtered_tables
from ai_modules.generator import generate_sql_from_text
from ai_modules.verifier import verify_sql_intent
from validators.intent_classifier import classify_intent, extract_mutation_details, detect_table_creation_intent
from validators.sql_validator import validate_sql
from validators.sql_detector import is_sql_query
from validators.dialect_validator import validate_dialect_compatibility
from ai_modules.interpreter import interpret_query_result
from ai_modules.followup_generator import generate_followup_questions
from ai_modules.context_analyzer import extract_query_context
from services import insight_service, onboarding_service
from services.policy_rag_service import policy_rag_service
from fastapi import UploadFile, File, Form

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class PolicyConfigThresholdRequest(BaseModel):
    threshold: float




class QueryRequest(BaseModel):
    query: str

class DetectModeRequest(BaseModel):
    query: str

class VerifyRequest(BaseModel):
    query: str
    sql: str

class ValidateRequest(BaseModel):
    sql: str

class ExecuteRequest(BaseModel):
    sql: str
    natural_query: Optional[str] = None
    is_direct_sql: bool = False
    is_verified: bool = False

class CRUDExecuteRequest(BaseModel):
    operation: str
    table: str
    fields: Dict[str, Any]
    where: Optional[Dict[str, Any]] = None

class ReuseRequest(BaseModel):
    query_id: int

class SelectDatabaseRequest(BaseModel):
    db_id: str

class TestConnectionRequest(BaseModel):
    connection_uri: str

from config.deployment import get_deployment_config, require_capability
from validators.security import (
    create_access_token,
    get_current_user,
    enforce_permission,
    enforce_manage_users,
    get_current_user_optional,
    enforce_suadmin,
    enforce_platform_master,
    enforce_org_suadmin,
)
from services.metadata_service import metadata_service
from pydantic import BaseModel, Field
from database.metadata_db import verify_password
from config.deployment import get_deployment_config
from database.metadata_db import STATUS_PENDING, STATUS_ACTIVE, STATUS_SUSPENDED, STATUS_REJECTED

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    organization: Optional[str] = None

class SetupAdminRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "VIEWER"

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1)
    organization: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    confirm_password: str = Field(..., min_length=1)

class OrganizationStatusRequest(BaseModel):
    status: Optional[str] = None

class AccountStatusRequest(BaseModel):
    status: str

class AssignRoleRequest(BaseModel):
    user_id: int
    role: str

class TargetLLMConfigInput(BaseModel):
    provider_type: str
    endpoint: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None

class LLMConfigRequest(BaseModel):
    generator: TargetLLMConfigInput
    verifier: TargetLLMConfigInput

class TestLLMConnectionRequest(BaseModel):
    provider_type: str
    endpoint: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None

class CustomConnectionRequest(BaseModel):
    connection_uri: str
    name: Optional[str] = "Custom Database"

class RegisterExistingSQLiteRequest(BaseModel):
    file_path: str
    display_name: Optional[str] = None


class CreateTableColumn(BaseModel):
    name: str
    type: str
    length: Optional[int] = None
    primary_key: Optional[bool] = False

class CreateTableForeignKey(BaseModel):
    column: str
    ref_table: str
    ref_column: str
    on_delete: Optional[str] = "NO ACTION"
    on_update: Optional[str] = "NO ACTION"

class CreateTableRequest(BaseModel):
    table_name: str
    columns: List[CreateTableColumn]
    foreign_keys: Optional[List[CreateTableForeignKey]] = []


class InsightRequest(BaseModel):
    data: List[Dict[str, Any]]
    query: Optional[str] = None
    sql: Optional[str] = None

def suggest_visualization(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not data:
        return {
            "type": "table", 
            "metadata": {"numeric_columns": [], "categorical_columns": [], "time_columns": []}
        }
    
    keys = list(data[0].keys())
    numeric_cols = []
    categorical_cols = []
    time_cols = []
    
    for k in keys:
        v = data[0][k]
        # Heuristic detection
        if isinstance(v, (int, float)):
            numeric_cols.append(k)
        elif isinstance(v, str):
            # Check for common time strings
            k_lower = k.lower()
            if any(word in k_lower for word in ["date", "time", "created_at", "updated_at", "month", "year"]):
                time_cols.append(k)
            else:
                categorical_cols.append(k)
        elif isinstance(v, (datetime.date, datetime.datetime)):
            time_cols.append(k)
            
    metadata = {
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "time_columns": time_cols
    }
    
    # Rules
    # 1. Time series -> Line
    if time_cols and numeric_cols:
        return {"type": "line", "metadata": metadata}
    
    # 2. 1 Categorical + 1 Numeric -> Bar
    if len(categorical_cols) == 1 and len(numeric_cols) >= 1:
        # 3. Small set of categories -> Pie
        if len(data) <= 10:
             return {"type": "pie", "metadata": metadata}
        return {"type": "bar", "metadata": metadata}
        
    # 4. Fallback
    return {"type": "table", "metadata": metadata}

@router.get("/health")
async def api_health():
    cfg = get_deployment_config()
    return {
        "status": "ok",
        "service": "HADIL",
        "api_version": "1.0",
        "deployment_mode": cfg.mode,
    }

@router.get("/capabilities")
async def api_capabilities():
    return get_deployment_config().public_capabilities()

@router.get("/setup/status")
async def get_setup_status_endpoint():
    status = metadata_service.get_setup_status()
    return status

@router.get("/databases")
async def get_databases(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    all_dbs = db_manager.list_databases()
    if not current_user:
        return all_dbs

    username = current_user["username"]
    user_id = int(current_user["sub"])
    cfg = get_deployment_config()

    if cfg.is_cloud:
        if metadata_service.is_platform_master_admin(user_id):
            return []
        user = metadata_service.get_user_by_id(user_id)
        if not user or not user.organization_id:
            return []
        meta_dbs = {d["id"]: d for d in metadata_service.list_registered_databases(user.organization_id)}
        allowed = []
        for db in all_dbs:
            if db["id"] not in meta_dbs:
                rec = metadata_service.get_database(db["id"])
                if not rec or rec.organization_id != user.organization_id:
                    continue
            role = metadata_service.get_user_role_for_database(user_id, db["id"])
            if role is not None:
                allowed.append(db)
        return allowed

    role_check = metadata_service.get_user_role_for_database(user_id, db_manager.current_db_id or "default")
    if role_check == "MASTER_ADMIN":
        return all_dbs

    allowed_dbs = []
    for db in all_dbs:
        role = metadata_service.get_user_role_for_database(user_id, db["id"])
        if role is not None:
            allowed_dbs.append(db)
    return allowed_dbs

@router.post("/select-database")
async def select_database(
    request: SelectDatabaseRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    username = current_user["username"]
    user_id = int(current_user["sub"])

    try:
        metadata_service.assert_customer_database_access(user_id, request.db_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    role = metadata_service.get_user_role_for_database(user_id, request.db_id)
    if not role:
        raise HTTPException(
            status_code=403,
            detail=f"Access Denied: User '{username}' does not have access to database '{request.db_id}'."
        )

    try:
        config = db_manager.set_database(request.db_id)
        models.HadilQueryHistory.__table__.create(bind=db_manager.engine, checkfirst=True)
        models.HadilDatabaseInsight.__table__.create(bind=db_manager.engine, checkfirst=True)
        onboarding_service.run_onboarding(request.db_id)

        return {"success": True, "message": f"Switched to {config['name']}", "db_id": request.db_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to switch database: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest):
    result = db_manager.test_connection(request.connection_uri)
    return result

@router.post("/connect-custom-db")
async def connect_custom_db(
    request: CustomConnectionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = int(current_user["sub"])
    cfg = get_deployment_config()
    user = metadata_service.get_user_by_id(user_id)
    if cfg.is_cloud:
        if not user or (user.organization_role or "").upper() != "SUADMIN":
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Only an organization SUADMIN can register a customer database.",
            )
    else:
        role = metadata_service.get_user_role_for_database(user_id, db_manager.current_db_id or "default")
        if role != "MASTER_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Only Master Administrator can connect or create new databases."
            )
    try:
        config = db_manager.set_custom_connection(request.connection_uri, name=request.name)
        if cfg.is_cloud and user and user.organization_id:
            metadata_service.register_or_update_database(
                db_id=config["id"],
                name=config.get("name") or request.name or config["id"],
                database_type="postgresql" if "postgres" in (request.connection_uri or "").lower() else "mysql",
                connection_uri=request.connection_uri,
                organization_id=user.organization_id,
            )
        # Create internal HADIL tracking tables only (do not attempt to create sample app models like User/Order/Product with bare String types on remote RDBMS)
        models.HadilQueryHistory.__table__.create(bind=db_manager.engine, checkfirst=True)
        models.HadilDatabaseInsight.__table__.create(bind=db_manager.engine, checkfirst=True)
        onboarding_service.run_onboarding(config["id"])

        return {"success": True, "message": f"Connected to {config['name']}", "db_id": config["id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to connect custom database: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/create-table")
async def create_table(
    request: CreateTableRequest,
    current_user: Dict[str, Any] = Depends(enforce_permission("ADD_TABLE"))
):
    if not db_manager.engine:
        raise HTTPException(status_code=400, detail="No active database engine connected.")

    table_name = request.table_name.strip()
    if not table_name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        raise HTTPException(status_code=400, detail="Invalid table name. Use alphanumeric characters and underscores only.")

    if not request.columns:
        raise HTTPException(status_code=400, detail="At least one column is required to create a table.")

    # Validate column uniqueness & format
    col_names = set()
    pk_count = 0
    valid_types = {"INTEGER", "BIGINT", "FLOAT", "DOUBLE", "DECIMAL", "BOOLEAN", "VARCHAR", "TEXT", "DATE", "DATETIME"}

    for col in request.columns:
        c_name = col.name.strip()
        if not c_name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", c_name):
            raise HTTPException(status_code=400, detail=f"Invalid column name '{col.name}'.")
        if c_name.lower() in col_names:
            raise HTTPException(status_code=400, detail=f"Duplicate column name '{c_name}' detected.")
        col_names.add(c_name.lower())

        c_type = col.type.upper().strip()
        if c_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Unsupported data type '{col.type}'.")

        if col.primary_key:
            pk_count += 1

    if pk_count > 1:
        raise HTTPException(status_code=400, detail="Multiple primary keys selected. Please select at most one primary key.")

    # Validate foreign keys if provided
    fk_constraints = []
    if request.foreign_keys:
        inspector = inspect(db_manager.engine)
        existing_tables_raw = inspector.get_table_names()
        existing_tables_map = {t.lower(): t for t in existing_tables_raw}

        seen_fk_pairs = set()

        for fk in request.foreign_keys:
            fk_col = fk.column.strip()
            ref_table_input = fk.ref_table.strip()
            ref_col_input = fk.ref_column.strip()

            # 1. Local column exists check
            if fk_col.lower() not in col_names:
                raise HTTPException(status_code=400, detail=f"Foreign key column '{fk_col}' does not exist in new table '{table_name}'.")

            # 2. Referenced table exists check
            if ref_table_input.lower() not in existing_tables_map:
                raise HTTPException(status_code=400, detail=f"Referenced table '{ref_table_input}' does not exist in active database.")
            actual_ref_table = existing_tables_map[ref_table_input.lower()]

            # 3. Referenced column exists check
            ref_cols_info = inspector.get_columns(actual_ref_table)
            ref_cols_map = {c["name"].lower(): c["name"] for c in ref_cols_info}
            if ref_col_input.lower() not in ref_cols_map:
                raise HTTPException(status_code=400, detail=f"Referenced column '{ref_col_input}' does not exist in referenced table '{actual_ref_table}'.")
            actual_ref_col = ref_cols_map[ref_col_input.lower()]

            # 4. Duplicate relationship check
            fk_pair = (fk_col.lower(), actual_ref_table.lower(), actual_ref_col.lower())
            if fk_pair in seen_fk_pairs:
                raise HTTPException(status_code=400, detail=f"Duplicate foreign key constraint on '{fk_col}' -> '{actual_ref_table}.{actual_ref_col}'.")
            seen_fk_pairs.add(fk_pair)

            # Build ForeignKeyConstraint with optional referential actions
            on_del = fk.on_delete.upper() if fk.on_delete else "NO ACTION"
            on_upd = fk.on_update.upper() if fk.on_update else "NO ACTION"

            fk_constraints.append(
                ForeignKeyConstraint(
                    [fk_col],
                    [f"{actual_ref_table}.{actual_ref_col}"],
                    ondelete=on_del if on_del != "NO ACTION" else None,
                    onupdate=on_upd if on_upd != "NO ACTION" else None
                )
            )

    # Construct SQLAlchemy Table & Columns dynamically
    sa_types = {
        "INTEGER": Integer,
        "BIGINT": BigInteger,
        "FLOAT": Float,
        "DOUBLE": Float,
        "DECIMAL": Numeric,
        "BOOLEAN": Boolean,
        "VARCHAR": String,
        "TEXT": Text,
        "DATE": Date,
        "DATETIME": DateTime
    }

    try:
        metadata = MetaData()
        sa_columns = []

        for col in request.columns:
            c_name = col.name.strip()
            c_type_str = col.type.upper().strip()
            sa_type_cls = sa_types[c_type_str]

            if c_type_str == "VARCHAR":
                length = col.length if (col.length and col.length > 0) else 255
                column_type = sa_type_cls(length)
            else:
                column_type = sa_type_cls()

            sa_columns.append(
                Column(
                    c_name,
                    column_type,
                    primary_key=bool(col.primary_key)
                )
            )

        table_args = sa_columns + fk_constraints
        # Reflect existing tables into metadata so ForeignKeyConstraint references resolve
        try:
            metadata.reflect(bind=db_manager.engine)
        except Exception as ref_err:
            logger.warning(f"Metadata reflect warning during create_table: {ref_err}")
        new_table = Table(table_name, metadata, *table_args)
        metadata.create_all(bind=db_manager.engine)

        # Refresh database insights & onboarding schema cache
        onboarding_service.run_onboarding(db_manager.current_db_id)

        return {
            "success": True,
            "message": f"Table '{table_name}' created successfully in database '{db_manager.current_db_name}'.",
            "table_name": table_name
        }
    except Exception as e:
        logger.error(f"Failed to create table '{table_name}': {e}")
        raise HTTPException(status_code=400, detail=f"Failed to create table: {str(e)}")


@router.get("/database-insights")
async def get_database_insights():
    if not db_manager.current_db_id:
        return {"summary": None, "suggested_queries": [], "tables": [], "stats": {"table_count": 0, "record_count": 0, "relation_count": 0}}
    
    insights = onboarding_service.get_onboarding_insights(db_manager.current_db_id)
    if not insights:
        # Try to run onboarding if schema exists
        onboarding_service.run_onboarding(db_manager.current_db_id)
        insights = onboarding_service.get_onboarding_insights(db_manager.current_db_id)
    
    tables = get_filtered_tables(db_manager.engine)
    stats = onboarding_service.get_database_stats()
    
    if not insights:
        insights = {
            "database_name": db_manager.current_db_id,
            "summary": "No tables discovered in this database." if not tables else "Database schema inspected.",
            "suggested_queries": [],
            "stats": stats
        }
    else:
        insights["stats"] = stats
    
    insights["tables"] = tables
    return insights

@router.get("/schema/tables")
async def get_schema_tables():
    try:
        tables = get_filtered_tables(db_manager.engine)
        return {"tables": tables}
    except Exception as e:
        return {"tables": [], "error": str(e)}

@router.get("/schema/table-details")
async def get_schema_table_details():
    try:
        if not db_manager.engine:
            return {"tables": {}}
        inspector = inspect(db_manager.engine)
        tables = get_filtered_tables(db_manager.engine)
        table_details = {}
        for t in tables:
            cols_info = inspector.get_columns(t)
            table_details[t] = [c["name"] for c in cols_info]
        return {"tables": table_details}
    except Exception as e:
        logger.error(f"Failed to fetch table details: {e}")
        return {"tables": {}, "error": str(e)}

@router.get("/current-database")
async def get_current_database():
    config = db_manager.get_database_config(db_manager.current_db_id)
    return {"id": db_manager.current_db_id, "name": config["name"] if config else "Unknown"}

@router.post("/generate-insights")
async def generate_insights_endpoint(request: InsightRequest):
    insights = insight_service.generate_insights(request.data, query=request.query, sql=request.sql)
    return {"insights": insights}

@router.post("/detect-mode")
async def detect_mode(request: DetectModeRequest):
    is_sql = is_sql_query(request.query)
    return {"mode": "SQL" if is_sql else "NL"}

@router.post("/predict-trend")
async def predict_trend_endpoint(request: InsightRequest):
    prediction = insight_service.predict_trend(request.data, query=request.query, sql=request.sql)
    return prediction

@router.post("/generate-sql")
async def generate_sql(request: QueryRequest):
    logger.info(f"--- Stage 1: Generation ---")
    logger.info(f"User Input: {request.query}")
    try:
        from validators.intent_classifier import detect_schema_metadata_intent
        schema_intent = detect_schema_metadata_intent(request.query)
        if schema_intent:
            stype = schema_intent["type"]
            logger.info(f"[HADIL QUERY DEBUG] Classified intent: SCHEMA_METADATA ({stype})")
            if stype == "TABLE_COUNT":
                sql = "-- HADIL SCHEMA METADATA: TABLE_COUNT"
                intent = "Count of active database tables from schema metadata"
            elif stype == "TABLE_LIST":
                sql = "-- HADIL SCHEMA METADATA: TABLE_LIST"
                intent = "List of active database tables from schema metadata"
            elif stype == "RELATIONSHIP_COUNT":
                sql = "-- HADIL SCHEMA METADATA: RELATIONSHIP_COUNT"
                intent = "Count of foreign key constraints from schema metadata"
            elif stype == "COLUMN_LIST":
                tname = schema_intent.get("target", "")
                sql = f"-- HADIL SCHEMA METADATA: COLUMN_LIST for {tname}"
                intent = f"Column list for table {tname} from schema metadata"
            else:
                sql = "-- HADIL SCHEMA METADATA"
                intent = "Schema metadata query"

            return {"sql": sql, "intent": intent, "is_ambiguous": False, "policy_context_supplied": False}

        # Perform Policy RAG Retrieval ONCE on server-side based on active DB scope
        active_db_id = db_manager.current_db_id
        policy_context, diagnostics = policy_rag_service.retrieve_policy_context(request.query, active_db_id=active_db_id)
        
        dialect = db_manager.engine.name if db_manager.engine else "sqlite"
        sql, intent, is_ambiguous, options = generate_sql_from_text(request.query, dialect=dialect, policy_context=policy_context)
        if is_ambiguous:
            return {
                "is_ambiguous": True,
                "intent": intent,
                "options": options,
                "message": f"Ambiguity detected: {intent}. Possible options: {', '.join(options)}"
            }

        from validators.sql_sanitizer import quote_sql_identifiers
        quoted_sql = quote_sql_identifiers(sql, engine=db_manager.engine)
        return {"sql": quoted_sql, "intent": intent, "is_ambiguous": False, "policy_context_supplied": bool(policy_context)}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-sql")
async def verify_sql(request: VerifyRequest):
    logger.info(f"--- Stage 2: Verification ---")
    logger.info(f"User Query: {request.query}")
    logger.info(f"Generated SQL: {request.sql}")
    
    active_db_id = db_manager.current_db_id
    policy_context, _ = policy_rag_service.retrieve_policy_context(request.query, active_db_id=active_db_id)
    
    result = verify_sql_intent(request.query, request.sql, policy_context=policy_context)
    logger.info(f"Verification Result: {result}")
    return result


@router.post("/validate-sql")
async def validate_sql_endpoint(request: ValidateRequest, is_direct_sql: bool = False):
    logger.info(f"--- Stage 3: Validation ---")
    logger.info(f"SQL for validation: {request.sql} (Direct: {is_direct_sql})")
    
    is_safe, warnings, errors = validate_sql(request.sql, is_direct_sql=is_direct_sql)
    
    # New: Dialect compatibility check
    dialect = db_manager.engine.name if db_manager.engine else "sqlite"
    is_compatible, dialect_errors = validate_dialect_compatibility(request.sql, dialect)
    
    if not is_compatible:
        is_safe = False
        errors.extend(dialect_errors)

    result = {
        "is_safe": is_safe,
        "warnings": warnings,
        "errors": errors,
        "dialect": dialect
    }
    logger.info(f"Validation Result: {result}")
    return result

@router.post("/auth/login")
async def login(request: LoginRequest):
    try:
        user = metadata_service.authenticate_user(
            request.username,
            request.password,
            organization=request.organization,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_access_token(user_id=user.id, username=user.username)
    return {"access_token": token, "token_type": "bearer", "username": user.username, "user_id": user.id}

@router.post("/auth/signup")
async def signup(request: SignupRequest):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Organization signup is only available in cloud deployment.")
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    try:
        result = metadata_service.signup_organization(
            username=request.username,
            organization_name=request.organization,
            password_raw=request.password,
        )
        return {"success": True, "message": "Registration submitted and is pending platform approval.", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = int(current_user["sub"])
    return metadata_service.build_auth_identity(
        user_id=user_id,
        jwt_username=current_user.get("username"),
        active_db_id=db_manager.current_db_id,
    )

@router.get("/users")
async def list_users_endpoint(
    current_user: Dict[str, Any] = Depends(enforce_manage_users)
):
    users = metadata_service.list_users()
    cfg = get_deployment_config()
    actor_id = int(current_user["sub"])
    if cfg.is_cloud:
        actor = metadata_service.get_user_by_id(actor_id)
        if metadata_service.is_platform_master_admin(actor_id):
            return [u for u in users if not u.get("organization_id")]
        if actor and actor.organization_id:
            users = [u for u in users if u.get("organization_id") == actor.organization_id]
        else:
            users = []
    return users

@router.post("/users/reset-and-seed")
async def reset_and_seed_users_endpoint(
    current_user: Dict[str, Any] = Depends(enforce_permission("MANAGE_USERS"))
):
    """
    Deletes all users and creates dedicated separate ADMIN users for each database.
    """
    if get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="User reset-and-seed is not available in cloud deployment.")
    created = metadata_service.reset_and_seed_per_db_admins()
    return {"success": True, "message": "All users reset. Dedicated DB admins created.", "users": created}

@router.post("/users")
async def create_user_endpoint(
    request: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(enforce_manage_users)
):
    try:
        actor_id = int(current_user["sub"])
        cfg = get_deployment_config()
        target_role = (request.role or "VIEWER").upper()
        if target_role in ("MASTER_ADMIN", "SUADMIN"):
            raise HTTPException(status_code=403, detail="Cannot create MASTER_ADMIN or SUADMIN through user management.")

        if cfg.is_cloud:
            db_id = db_manager.current_db_id
            db_role = target_role if db_id else None
            new_user = metadata_service.create_organization_user(
                actor_user_id=actor_id,
                local_username=request.username,
                password_raw=request.password,
                database_id=db_id,
                db_role=db_role,
            )
            return {"success": True, "user_id": new_user.id, "username": new_user.username}

        user_role = metadata_service.get_user_role_for_database(actor_id, db_manager.current_db_id or "default")
        is_master = user_role == "MASTER_ADMIN"

        if target_role == "ADMIN" and not is_master:
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Only a Master Admin can create or assign ADMIN roles."
            )
        if target_role == "ADMIN" and not db_manager.current_db_id:
            raise HTTPException(status_code=400, detail="No active database selected.")

        new_user = metadata_service.create_user(request.username, request.password)
        if db_manager.current_db_id and target_role:
            metadata_service.assign_user_role(new_user.id, db_manager.current_db_id, target_role)
        return {"success": True, "user_id": new_user.id, "username": new_user.username}
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/users/{user_id}/roles")
async def assign_role_endpoint(
    user_id: int,
    request: AssignRoleRequest,
    current_user: Dict[str, Any] = Depends(enforce_manage_users)
):
    if not db_manager.current_db_id:
        raise HTTPException(status_code=400, detail="No active database selected.")

    actor_id = int(current_user["sub"])
    cfg = get_deployment_config()
    target_role = request.role.upper()
    if target_role in ("MASTER_ADMIN", "SUADMIN"):
        raise HTTPException(status_code=403, detail="Cannot assign MASTER_ADMIN or SUADMIN as a database role.")

    if cfg.is_cloud:
        try:
            metadata_service.assert_customer_database_access(actor_id, db_manager.current_db_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        target_user = metadata_service.get_user_by_id(user_id)
        actor = metadata_service.get_user_by_id(actor_id)
        if not target_user or not actor or target_user.organization_id != actor.organization_id:
            raise HTTPException(status_code=403, detail="Cannot assign roles to users outside this organization.")
        actor_role = metadata_service.get_user_role_for_database(actor_id, db_manager.current_db_id)
        is_suadmin = actor and (actor.organization_role or "").upper() == "SUADMIN"
        if target_role == "ADMIN" and not is_suadmin:
            raise HTTPException(
                status_code=403,
                detail="Access Denied: Only an organization SUADMIN can assign ADMIN roles."
            )
        try:
            role_rec = metadata_service.assign_user_role(user_id, db_manager.current_db_id, target_role)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return {"success": True, "user_id": user_id, "database_id": db_manager.current_db_id, "role": role_rec.role}

    user_role = metadata_service.get_user_role_for_database(actor_id, db_manager.current_db_id or "default")
    is_master = user_role == "MASTER_ADMIN"

    if target_role == "ADMIN" and not is_master:
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Only a Master Admin can assign ADMIN roles."
        )

    role_rec = metadata_service.assign_user_role(user_id, db_manager.current_db_id, target_role)
    return {"success": True, "user_id": user_id, "database_id": db_manager.current_db_id, "role": role_rec.role}

@router.post("/execute-query")
async def execute_query(
    request: ExecuteRequest, 
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(enforce_permission("READ"))
):
    logger.info(f"--- Stage 4: Execution ---")
    logger.info(f"SQL for execution: {request.sql}")
    
    from validators.intent_classifier import detect_schema_metadata_intent
    schema_intent = detect_schema_metadata_intent(request.natural_query or "") or detect_schema_metadata_intent(request.sql or "")
    if request.sql and request.sql.startswith("-- HADIL SCHEMA METADATA"):
        if not schema_intent:
            if "TABLE_COUNT" in request.sql:
                schema_intent = {"type": "TABLE_COUNT"}
            elif "TABLE_LIST" in request.sql:
                schema_intent = {"type": "TABLE_LIST"}
            elif "RELATIONSHIP_COUNT" in request.sql:
                schema_intent = {"type": "RELATIONSHIP_COUNT"}
            elif "COLUMN_LIST" in request.sql:
                parts = request.sql.split("for ")
                t_target = parts[1].strip() if len(parts) > 1 else ""
                schema_intent = {"type": "COLUMN_LIST", "target": t_target}

    if schema_intent:
        stype = schema_intent["type"]
        tables = get_filtered_tables(db_manager.engine)
        logger.info(f"[HADIL QUERY DEBUG] Executing deterministic schema query: {stype} against active DB '{db_manager.current_db_id}'")
        
        if stype == "TABLE_COUNT":
            count = len(tables)
            data = [{"table_count": count}]
            interpreted = f"Your database has {count} table{'s' if count != 1 else ''}."
            return {
                "success": True,
                "data": data,
                "interpreted_answer": interpreted,
                "columns": ["table_count"],
                "suggested_visualization": "STAT_CARD",
                "metadata": {"title": "Database Table Count"},
                "followup_suggestions": ["What tables are in my database?", "How many relationships exist?"]
            }
        elif stype == "TABLE_LIST":
            data = [{"table_name": t} for t in tables]
            if tables:
                interpreted = f"Your database contains {len(tables)} table{'s' if len(tables) != 1 else ''}: {', '.join(tables)}."
            else:
                interpreted = "Your database contains no tables."
            return {
                "success": True,
                "data": data,
                "interpreted_answer": interpreted,
                "columns": ["table_name"],
                "suggested_visualization": "TABLE",
                "metadata": {"title": "Database Tables"},
                "followup_suggestions": ["How many tables does my database have?", "How many relationships exist?"]
            }
        elif stype == "RELATIONSHIP_COUNT":
            rel_count = 0
            if db_manager.engine:
                try:
                    inspector = inspect(db_manager.engine)
                    for t in tables:
                        rel_count += len(inspector.get_foreign_keys(t))
                except Exception:
                    pass
            data = [{"relationship_count": rel_count}]
            interpreted = f"Your database has {rel_count} foreign key relationship{'s' if rel_count != 1 else ''}."
            return {
                "success": True,
                "data": data,
                "interpreted_answer": interpreted,
                "columns": ["relationship_count"],
                "suggested_visualization": "STAT_CARD",
                "metadata": {"title": "Relationship Count"},
                "followup_suggestions": ["What tables are in my database?", "How many tables does my database have?"]
            }
        elif stype == "COLUMN_LIST":
            tname = schema_intent.get("target", "").strip()
            cols = []
            matched_t = next((t for t in tables if t.lower() == tname.lower()), tname)
            if db_manager.engine and matched_t:
                try:
                    inspector = inspect(db_manager.engine)
                    cols = [c["name"] for c in inspector.get_columns(matched_t)]
                except Exception:
                    pass
            data = [{"column_name": c} for c in cols]
            if cols:
                interpreted = f"Table '{matched_t}' has {len(cols)} column{'s' if len(cols) != 1 else ''}: {', '.join(cols)}."
            else:
                interpreted = f"No columns found for table '{tname}'."
            return {
                "success": True,
                "data": data,
                "interpreted_answer": interpreted,
                "columns": ["column_name"],
                "suggested_visualization": "TABLE",
                "metadata": {"title": f"Columns for {matched_t or tname}"},
                "followup_suggestions": ["How many tables does my database have?", "What tables are in my database?"]
            }
    
    # Backend Centralized AI Verification Security Gate
    if not request.is_verified:
        logger.info(f"Executing backend AI Verification for query: {request.sql}")
        active_db_id = db_manager.current_db_id
        policy_context, _ = policy_rag_service.retrieve_policy_context(request.natural_query or request.sql, active_db_id=active_db_id)
        verification_res = verify_sql_intent(request.natural_query or request.sql, request.sql, policy_context=policy_context)
        if not verification_res.get("is_valid", False):
            explanation = verification_res.get("explanation", "AI Verification rejected the query.")
            logger.warning(f"AI Verification blocked execution: {request.sql}. Reason: {explanation}")
            return {"success": False, "error": f"AI Verification failed: {explanation}", "details": verification_res.get("errors", [])}


    # Extra safety check before execution even if validator passed
    # Only allow SELECT for non-direct or if direct but failed basic check
    sql_clean = request.sql.strip().lower()
    is_select = sql_clean.startswith("select") or sql_clean.startswith("with")
    
    if not is_select and not request.is_direct_sql:
         logger.warning(f"Blocked non-SELECT query at execution stage: {request.sql}")
         return {"success": False, "error": "AI-generated queries are restricted to SELECT operations."}
    
    # Final safety gate: Re-run validation just in case
    is_safe, _, errors = validate_sql(request.sql, is_direct_sql=request.is_direct_sql)
    
    # Dialect check in execution
    dialect = db_manager.engine.name if db_manager.engine else "sqlite"
    is_compatible, dialect_errors = validate_dialect_compatibility(request.sql, dialect)
    
    if not is_safe or not is_compatible:
        all_errors = errors + dialect_errors
        return {"success": False, "error": f"Safety or Compatibility validation failed: {', '.join(all_errors)}"}

    from validators.sql_sanitizer import quote_sql_identifiers
    exec_sql = quote_sql_identifiers(request.sql, engine=db_manager.engine)

    try:
        refl_tables = get_filtered_tables(db_manager.engine)
    except Exception:
        refl_tables = []

    print(f"[HADIL SQL TRACE] Query: {request.natural_query or request.sql}")
    print(f"[HADIL SQL TRACE] Generated SQL: {request.sql}")
    print(f"[HADIL SQL TRACE] Sanitized SQL: {exec_sql}")
    print(f"[HADIL SQL TRACE] SQL submitted to execution: {exec_sql}")
    print(f"[HADIL SQL TRACE] Dialect: {dialect}")
    print(f"[HADIL SQL TRACE] Tables: {refl_tables}")

    logger.info(f"[HADIL SQL DEBUG] Incoming SQL: {request.sql}")
    logger.info(f"[HADIL SQL DEBUG] Sanitized SQL: {exec_sql}")
    logger.info(f"[HADIL SQL DEBUG] Active dialect: {dialect}")
    logger.info(f"[HADIL SQL DEBUG] Reflected tables: {refl_tables}")

    try:
        result = db.execute(text(exec_sql))
        rows = result.fetchall()
        data = [dict(row._mapping) for row in rows]
        
        # Suggest visualization
        viz_result = suggest_visualization(data)
        
        # Interpret result for small datasets (analytics)
        interpreted_answer = None
        if request.natural_query and len(data) <= 5:
            interpreted_answer = interpret_query_result(request.natural_query, data)
        
        # Log to history if natural_query is provided (SUCCESS ONLY)
        if request.natural_query:
            import datetime
            existing = db.query(models.HadilQueryHistory).filter(
                models.HadilQueryHistory.sql_query == request.sql
            ).first()
            
            if existing:
                existing.usage_count += 1
                existing.last_used = datetime.datetime.utcnow()
                existing.is_valid = 1
            else:
                new_hist = models.HadilQueryHistory(
                    natural_query=request.natural_query,
                    sql_query=request.sql,
                    is_valid=1
                )
                db.add(new_hist)
            db.commit()

            # Dual-log to HADIL Metadata DB (scoped by active_database_id)
            try:
                from services.metadata_service import metadata_service
                if db_manager.current_db_id:
                    metadata_service.log_query_history(
                        database_id=db_manager.current_db_id,
                        query=request.natural_query or request.sql,
                        operation="SELECT",
                        status="SUCCESS"
                    )
            except Exception as meta_log_err:
                logger.warning(f"Could not dual-log query to Metadata DB: {meta_log_err}")

        # Generate Follow-up Questions
        followup_suggestions = []
        if request.natural_query:
            # Re-use or extract context
            query_context = extract_query_context(request.natural_query, request.sql)
            if query_context:
                followup_suggestions = generate_followup_questions(
                    request.natural_query, 
                    request.sql, 
                    query_context, 
                    list(data[0].keys()) if data else []
                )

        logger.info(f"Execution successful. Returned {len(data)} rows. Suggested: {viz_result['type']}")
        return {
            "success": True, 
            "data": data, 
            "interpreted_answer": interpreted_answer,
            "columns": list(data[0].keys()) if data else [],
            "suggested_visualization": viz_result["type"],
            "metadata": viz_result["metadata"],
            "followup_suggestions": followup_suggestions
        }
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return {"success": False, "error": str(e)}

@router.get("/queries/recent")
async def get_recent_queries(n: int = 5, db: Session = Depends(get_db)):
    queries = db.query(models.HadilQueryHistory).order_by(models.HadilQueryHistory.last_used.desc()).limit(n).all()
    return queries

@router.get("/queries/frequent")
async def get_frequent_queries(n: int = 5, db: Session = Depends(get_db)):
    queries = db.query(models.HadilQueryHistory).order_by(models.HadilQueryHistory.usage_count.desc()).limit(n).all()
    return queries

@router.post("/queries/reuse")
async def reuse_query(request: ReuseRequest, db: Session = Depends(get_db)):
    query_hist = db.query(models.HadilQueryHistory).filter(models.HadilQueryHistory.id == request.query_id).first()
    if not query_hist:
        raise HTTPException(status_code=404, detail="Query not found")
    
    # Still pass through safety validator
    is_safe, warnings, errors = validate_sql(query_hist.sql_query)
    if not is_safe:
        return {"success": False, "error": "Query failed safety validation", "details": errors}
    
    # Execute
    return await execute_query(ExecuteRequest(sql=query_hist.sql_query, natural_query=query_hist.natural_query), db=db)

@router.post("/generate-form")
async def generate_form(request: QueryRequest):
    logger.info(f"--- CRUD Stage: Deterministic Intent Detection ---")
    operation = classify_intent(request.query)
    
    if operation == "READ":
        return {"operation": "READ"}

    if operation == "CREATE_TABLE":
        table_creation_info = detect_table_creation_intent(request.query)
        extracted_name = table_creation_info.get("table_name", "") if table_creation_info else ""
        return {
            "operation": "CREATE_TABLE",
            "target_table_name": extracted_name
        }

    intent_data = extract_mutation_details(request.query, operation)
    if intent_data.get("operation") == "ERROR":
        return intent_data

    table_name = intent_data.get("table")
    if not table_name:
        return {"operation": "ERROR", "error": intent_data.get("error", "Could not determine target table for mutation.")}

    schema = get_table_schema(table_name)
    if not schema:
        return {"operation": "ERROR", "error": f"Table '{table_name}' not found in schema."}
    
    return {
        "operation": operation,
        "table": table_name,
        "form": {
            "fields": schema,
            "prefill": intent_data.get("fields", {}),
            "where": intent_data.get("where", {})
        }
    }

@router.post("/execute-form")
async def execute_form(
    request: CRUDExecuteRequest, 
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    logger.info(f"--- CRUD Stage: Execution ---")
    operation = request.operation.upper()
    table = request.table
    fields = request.fields
    where = request.where or {}

    # Map CRUD Operation to RBAC permission required
    permission_map = {
        "CREATE": "ADD",
        "INSERT": "ADD",
        "ADD": "ADD",
        "UPDATE": "UPDATE",
        "DELETE": "DELETE"
    }
    required_perm = permission_map.get(operation)
    if not required_perm:
        raise HTTPException(status_code=400, detail=f"Invalid CRUD operation '{operation}'.")

    # Enforce RBAC permission dynamically based on operation
    user_id = int(current_user["sub"])
    active_db_id = db_manager.current_db_id
    if not active_db_id:
        raise HTTPException(status_code=400, detail="No active database selected.")

    if not metadata_service.check_permission(user_id, active_db_id, required_perm):
        raise HTTPException(
            status_code=403, 
            detail=f"Access Denied: User '{current_user['username']}' lacks '{required_perm}' permission for operation '{operation}' on active database '{active_db_id}'."
        )

    try:
        dialect_preparer = db_manager.engine.dialect.identifier_preparer if db_manager.engine else None
        def safe_q(ident: str) -> str:
            if dialect_preparer and any(c.isupper() for c in ident):
                return dialect_preparer.quote(ident)
            return ident

        q_table = safe_q(table)

        if operation == "CREATE":
            cols = ", ".join([safe_q(k) for k in fields.keys()])
            placeholders = ", ".join([f":{k}" for k in fields.keys()])
            query = f"INSERT INTO {q_table} ({cols}) VALUES ({placeholders})"
            db.execute(text(query), fields)
            db.commit()
            return {"success": True, "message": f"Successfully created record in {table}."}
        
        elif operation == "UPDATE":
            if not where:
                 return {"success": False, "error": "UPDATE operation requires a WHERE clause for safety."}
            
            set_clause = ", ".join([f"{safe_q(k)} = :val_{k}" for k in fields.keys()])
            where_clause = " AND ".join([f"{safe_q(k)} = :where_{k}" for k in where.keys()])
            
            params = {f"val_{k}": v for k, v in fields.items()}
            params.update({f"where_{k}": v for k, v in where.items()})
            
            query = f"UPDATE {q_table} SET {set_clause} WHERE {where_clause}"
            db.execute(text(query), params)
            db.commit()
            return {"success": True, "message": f"Successfully updated record(s) in {table}."}

        elif operation == "DELETE":
            if not where:
                 return {"success": False, "error": "DELETE operation requires a WHERE clause for safety."}
            
            where_clause = " AND ".join([f"{safe_q(k)} = :where_{k}" for k in where.keys()])
            params = {f"where_{k}": v for k, v in where.items()}
            
            query = f"DELETE FROM {q_table} WHERE {where_clause}"
            db.execute(text(query), params)
            db.commit()
            return {"success": True, "message": f"Successfully deleted record(s) from {table}."}
        
        else:
            return {"success": False, "error": f"Unsupported operation: {operation}"}
            
    except Exception as e:
        logger.error(f"CRUD Execution failed: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

# --- Admin LLM Configuration Endpoints ---
@router.get("/admin/llm-config")
def get_llm_configuration(
    current_user: dict = Depends(enforce_suadmin)
):
    gen_config = metadata_service.get_llm_config("generator")
    ver_config = metadata_service.get_llm_config("verifier")
    return {
        "generator": {
            "target": gen_config.get("target"),
            "provider_type": gen_config.get("provider_type"),
            "endpoint": gen_config.get("endpoint"),
            "model": gen_config.get("model"),
            "api_key_configured": gen_config.get("api_key_configured", False)
        },
        "verifier": {
            "target": ver_config.get("target"),
            "provider_type": ver_config.get("provider_type"),
            "endpoint": ver_config.get("endpoint"),
            "model": ver_config.get("model"),
            "api_key_configured": ver_config.get("api_key_configured", False)
        }
    }

@router.post("/admin/llm-config")
def update_llm_configuration(
    req: LLMConfigRequest,
    current_user: dict = Depends(enforce_suadmin)
):
    # Retrieve current configs to preserve backend model & api_key when provider is changed from frontend
    curr_gen = metadata_service.get_llm_config_internal("generator")
    curr_ver = metadata_service.get_llm_config_internal("verifier")

    gen_res = metadata_service.set_llm_config(
        target="generator",
        provider_type=req.generator.provider_type,
        endpoint=req.generator.endpoint if req.generator.provider_type in ["custom", "ollama", "qwen"] else (req.generator.endpoint or None),
        model=req.generator.model or curr_gen.get("model"),
        api_key=req.generator.api_key or "••••••••"
    )
    ver_res = metadata_service.set_llm_config(
        target="verifier",
        provider_type=req.verifier.provider_type,
        endpoint=req.verifier.endpoint if req.verifier.provider_type in ["custom", "ollama", "qwen"] else (req.verifier.endpoint or None),
        model=req.verifier.model or curr_ver.get("model"),
        api_key=req.verifier.api_key or "••••••••"
    )

    return {
        "message": "AI Provider selection updated successfully.",
        "generator": {
            "target": gen_res.get("target"),
            "provider_type": gen_res.get("provider_type"),
            "api_key_configured": gen_res.get("api_key_configured", False)
        },
        "verifier": {
            "target": ver_res.get("target"),
            "provider_type": ver_res.get("provider_type"),
            "api_key_configured": ver_res.get("api_key_configured", False)
        }
    }

@router.post("/admin/llm-config/test")
def test_llm_connection(
    req: TestLLMConnectionRequest,
    current_user: dict = Depends(enforce_suadmin)
):
    from ai_modules.providers import CustomProvider, OpenAIProvider, QwenProvider
    p_type = req.provider_type.lower().strip()
    
    if p_type == "custom":
        provider = CustomProvider(
            endpoint=req.endpoint or "",
            model=req.model or "custom-model",
            api_key=req.api_key
        )
    elif p_type in ["qwen", "ollama"]:
        provider = QwenProvider(
            model=req.model,
            endpoint=req.endpoint
        )
    elif p_type == "openai":
        provider = OpenAIProvider(
            model=req.model,
            api_key=req.api_key
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider type '{req.provider_type}'")

    res = provider.health_check()
    return res

class AddDirectoryRequest(BaseModel):
    path: str

# --- Admin Database Import & Registration Endpoints ---
@router.post("/admin/databases/register-path")
def register_existing_sqlite_path(
    req: RegisterExistingSQLiteRequest,
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("sqlite_file_location")),
):
    """
    SuAdmin-only endpoint to validate and register an existing SQLite database file
    located on the HADIL server filesystem.
    """
    if not req.file_path or not req.file_path.strip():
        raise HTTPException(status_code=400, detail="Database file path is required.")
    
    clean_path = req.file_path.strip()
    try:
        res = metadata_service.register_sqlite_file_database(
            file_path=clean_path,
            display_name=req.display_name,
            is_managed_upload=False
        )
        return {
            "success": True,
            "message": f"Successfully registered SQLite database '{res['name']}'.",
            "database": res
        }
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        logger.error(f"Error registering existing SQLite database path: {e}")
        raise HTTPException(status_code=500, detail="Failed to register database file.")

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

@router.post("/admin/databases/upload")
async def upload_sqlite_database(
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("sqlite_upload")),
):

    """
    SuAdmin-only endpoint to upload, validate, store under %APPDATA%/HADIL/databases,
    and register a SQLite database file.
    """
    # 1. Extension & Name Validation
    filename = file.filename or "uploaded.db"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".db", ".sqlite", ".sqlite3"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Uploaded file must be a SQLite database (.db, .sqlite, .sqlite3)."
        )

    # 2. Destination Setup under HADIL-managed storage
    from utils.path_resolver import get_default_database_folder
    storage_folder = get_default_database_folder()
    os.makedirs(storage_folder, exist_ok=True)

    safe_filename = f"upload_{uuid.uuid4().hex[:12]}{ext}"
    dest_path = os.path.join(storage_folder, safe_filename)

    # 3. Stream Upload with Size Limit (500MB max)
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB
    bytes_written = 0

    try:
        with open(dest_path, "wb") as f_out:
            while chunk := await file.read(1024 * 1024): # 1MB chunks
                bytes_written += len(chunk)
                if bytes_written > MAX_FILE_SIZE:
                    f_out.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=400,
                        detail="Uploaded database file exceeds maximum allowed size limit (500MB)."
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        logger.error(f"Error saving uploaded database file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded database file on server.")

    # 4. Validate & Register Managed Database
    friendly_name = display_name.strip() if (display_name and display_name.strip()) else os.path.splitext(os.path.basename(filename))[0]
    
    try:
        res = metadata_service.register_sqlite_file_database(
            file_path=dest_path,
            display_name=friendly_name,
            is_managed_upload=True
        )
        return {
            "success": True,
            "message": f"Database '{res['name']}' uploaded and registered successfully.",
            "database": res
        }
    except ValueError as val_err:
        # Cleanup failed upload file
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        logger.error(f"Error registering uploaded SQLite database: {e}")
        raise HTTPException(status_code=500, detail="Failed to register uploaded database.")

# --- Admin Server Control Endpoints ---

@router.post("/admin/server/shutdown")
def shutdown_server_endpoint(
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("server_shutdown")),
):
    """
    SuAdmin-only endpoint to trigger a graceful HADIL application server shutdown.
    """
    logger.info(f"[HADIL RUNTIME] Server shutdown initiated by SuAdmin user '{current_user.get('username')}'.")
    from hadil_runtime import shutdown_active_runtime
    # Trigger background thread graceful shutdown after a slight delay to allow response delivery
    import threading
    threading.Thread(target=shutdown_active_runtime, kwargs={"delay_seconds": 0.5}, daemon=True).start()
    return {
        "success": True,
        "message": "HADIL server shutdown initiated successfully."
    }

# --- Admin Database Directory Management Endpoints ---
@router.get("/admin/db-directories")
def list_db_directories_endpoint(
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("sqlite_directory_scan")),
):

    dirs = metadata_service.list_db_directories()
    return {"directories": dirs}

@router.post("/admin/db-directories")
def add_db_directory_endpoint(
    req: AddDirectoryRequest,
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("sqlite_directory_scan")),
):
    if not req.path or not req.path.strip():
        raise HTTPException(status_code=400, detail="Directory path cannot be empty.")
    try:
        added = metadata_service.add_db_directory(req.path.strip())
        db_manager.scan_configured_directories()
        return {"success": True, "message": f"Added database directory: {added}", "directory": added}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/admin/db-directories")
def remove_db_directory_endpoint(
    path: str,
    current_user: dict = Depends(enforce_suadmin),
    _caps=Depends(require_capability("sqlite_directory_scan")),
):
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Directory path cannot be empty.")
    try:
        removed = metadata_service.remove_db_directory(path.strip())
        if not removed:
            raise HTTPException(status_code=404, detail=f"Directory path '{path}' not found in configuration.")
        db_manager.scan_configured_directories()
        return {"success": True, "message": f"Removed database directory: {path}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Admin System Status Diagnostic Endpoint ---
@router.get("/admin/system-status")
def get_system_status_endpoint(
    current_user: dict = Depends(enforce_suadmin)
):
    from database.metadata_db import metadata_manager
    from database.manager import db_manager
    from services.policy_rag_service import policy_rag_service, FAISS_INDEX_PATH
    
    meta_db_ok = metadata_manager.is_healthy()
    db_mgr_ok = db_manager is not None
    rag_ok = policy_rag_service.is_initialized
    faiss_ok = os.path.exists(FAISS_INDEX_PATH)

    cfg = metadata_service.get_llm_config_internal("generator")
    provider = cfg.get("provider_type", "openai").title()
    model = cfg.get("model") or "default"

    dirs = metadata_service.list_db_directories()
    policy_count = len(metadata_service.list_policy_documents())

    return {
        "fastapi_status": "RUNNING",
        "metadata_db_status": "OK" if meta_db_ok else "FAILED",
        "database_manager_status": "OK" if db_mgr_ok else "FAILED",
        "policy_rag_status": "OK" if rag_ok else "FAILED",
        "faiss_index_status": "OK" if faiss_ok else "NOT FOUND",
        "llm_provider": provider,
        "llm_model": model,
        "configured_db_directories_count": len(dirs),
        "indexed_policy_count": policy_count
    }


# --- First-Run Setup Lock Endpoints ---
@router.get("/setup/status")
def get_setup_status():
    """
    Returns setup_required status based on HadilUser table count in metadata DB.
    """
    return metadata_service.get_setup_status()

@router.post("/setup/admin")
def create_first_admin(req: SetupAdminRequest):
    """
    Creates the first ADMIN user on fresh HADIL installation.
    Permanently locked once any user exists (returns 403 Forbidden).
    """
    if not req.username or not req.username.strip():
        raise HTTPException(status_code=400, detail="Username is required.")
    if not req.password or not req.password.strip():
        raise HTTPException(status_code=400, detail="Password is required.")

    status = metadata_service.get_setup_status()
    if not status.get("setup_required"):
        raise HTTPException(status_code=403, detail="Initial setup has already been completed.")

    try:
        user = metadata_service.create_first_admin(req.username.strip(), req.password)
        return {
            "success": True,
            "message": "First administrator account created successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": "ADMIN"
            }
        }
    except ValueError as val_err:
        raise HTTPException(status_code=403, detail=str(val_err))
    except Exception as e:
        logger.error(f"Error creating initial admin: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create initial admin: {str(e)}")

@router.get("/platform/organizations")
def list_platform_organizations(
    status: Optional[str] = None,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform organization administration is cloud-only.")
    return {"organizations": metadata_service.list_organizations(status=status)}

@router.post("/platform/organizations/{organization_id}/approve")
def approve_organization(
    organization_id: int,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform organization administration is cloud-only.")
    try:
        result = metadata_service.set_organization_status(organization_id, STATUS_ACTIVE)
        return {"success": True, "message": "Organization approved. First account is now SUADMIN.", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/platform/organizations/{organization_id}/reject")
def reject_organization(
    organization_id: int,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform organization administration is cloud-only.")
    try:
        result = metadata_service.set_organization_status(organization_id, STATUS_REJECTED)
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/platform/organizations/{organization_id}/suspend")
def suspend_organization(
    organization_id: int,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform organization administration is cloud-only.")
    try:
        result = metadata_service.set_organization_status(organization_id, STATUS_SUSPENDED)
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/platform/organizations/{organization_id}/reactivate")
def reactivate_organization(
    organization_id: int,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform organization administration is cloud-only.")
    try:
        result = metadata_service.set_organization_status(organization_id, STATUS_ACTIVE)
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/platform/users/{user_id}/status")
def set_platform_user_status(
    user_id: int,
    request: AccountStatusRequest,
    current_user: dict = Depends(enforce_platform_master),
):
    if not get_deployment_config().is_cloud:
        raise HTTPException(status_code=403, detail="Platform account administration is cloud-only.")
    try:
        user = metadata_service.set_user_account_status(user_id, request.status)
        return {"success": True, "user_id": user.id, "account_status": user.account_status}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# --- Admin Policy Management Endpoints ---
@router.post("/policies/upload")
async def upload_policy_document(
    file: UploadFile = File(...),
    scope: str = Form("GLOBAL"), # "GLOBAL" or "DATABASE:<db_id>"
    current_user: Dict[str, Any] = Depends(enforce_permission("MANAGE_USERS"))
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing.")

    ext = os.path.splitext(file.filename)[1].lower().replace(".", "")
    if ext not in ["pdf", "txt", "docx"]:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension '.{ext}'. Supported: .pdf, .txt, .docx")

    # Secure document ID and safe storage path
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    safe_filename = f"{doc_id}_{os.path.basename(file.filename)}"
    scope_clean = scope.strip().upper()
    if scope_clean != "GLOBAL" and not scope_clean.startswith("DATABASE:"):
        scope_clean = f"DATABASE:{scope_clean}"

    safe_dir = os.path.join("./storage/policies/original", scope_clean.replace(":", "_"))
    os.makedirs(safe_dir, exist_ok=True)
    target_file_path = os.path.abspath(os.path.join(safe_dir, safe_filename))

    # Path traversal check
    if not target_file_path.startswith(os.path.abspath("./storage/policies")):
        raise HTTPException(status_code=400, detail="Invalid target path (path traversal detected).")

    user_id = int(current_user["sub"])

    try:
        # Save file to disk
        contents = await file.read()
        with open(target_file_path, "wb") as f:
            f.write(contents)

        # 1. Create DB metadata record (PENDING)
        doc_rec = metadata_service.create_policy_document(
            doc_id=doc_id,
            filename=file.filename,
            doc_type=ext,
            scope=scope_clean,
            uploaded_by_user_id=user_id,
            file_path=target_file_path
        )

        # 2. Extract, chunk, embed, and index
        index_res = policy_rag_service.add_document(
            doc_id=doc_id,
            file_path=target_file_path,
            filename=file.filename,
            doc_type=ext,
            scope=scope_clean,
            uploaded_by_user_id=user_id
        )

        return {
            "success": True,
            "message": f"Successfully uploaded and indexed policy document '{file.filename}'.",
            "document": {
                "id": doc_rec.id,
                "filename": doc_rec.filename,
                "scope": doc_rec.scope,
                "chunk_count": index_res.get("chunk_count", 0),
                "indexing_status": "INDEXED"
            }
        }
    except Exception as e:
        logger.error(f"Failed to process uploaded policy document: {e}")
        if os.path.exists(target_file_path):
            try:
                os.remove(target_file_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Policy processing failed: {str(e)}")

@router.get("/policies")
async def list_policies(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    policies = metadata_service.list_policy_documents()
    return policies

@router.delete("/policies/{doc_id}")
async def delete_policy(
    doc_id: str,
    current_user: Dict[str, Any] = Depends(enforce_permission("MANAGE_USERS"))
):
    doc = metadata_service.get_policy_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Policy document '{doc_id}' not found.")

    try:
        # Delete original file if exists
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception as fe:
                logger.warning(f"Could not remove original policy file: {fe}")

        # Remove from vector index & chunk metadata
        policy_rag_service.delete_document(doc_id)

        # Remove from metadata database
        metadata_service.delete_policy_document(doc_id)

        return {"success": True, "message": f"Policy document '{doc.filename}' deleted successfully."}
    except Exception as e:
        logger.error(f"Failed to delete policy document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/policies/config")
async def get_policy_config(
    current_user: Dict[str, Any] = Depends(enforce_permission("MANAGE_USERS"))
):
    return {
        "threshold": policy_rag_service.threshold,
        "embedding_model": "all-MiniLM-L6-v2",
        "faiss_index_type": "IndexFlatIP (Cosine Similarity)"
    }

@router.post("/policies/config")
async def update_policy_config(
    req: PolicyConfigThresholdRequest,
    current_user: Dict[str, Any] = Depends(enforce_permission("MANAGE_USERS"))
):
    policy_rag_service.set_threshold(req.threshold)
    return {"success": True, "message": f"Policy threshold updated to {req.threshold}", "threshold": policy_rag_service.threshold}

@router.on_event("startup")
def startup():
    try:
        logger.info("Initializing database...")
        engine = get_engine()
        if not engine:
            logger.warning("No database engine initialized on startup. Skipping table DDL creation.")
            return

        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")


        # Initialize Policy RAG Subsystem (Load persisted FAISS index & metadata)
        try:
            logger.info("Initializing Policy RAG vector index...")
            policy_rag_service.initialize()
            logger.info("Policy RAG vector index ready.")
        except Exception as rag_err:
            logger.error(f"Policy RAG initialization warning: {rag_err}")

        
        # Seed data if empty
        db = db_manager.get_session()
        try:
            if db.query(models.User).count() == 0:
                logger.info("Seeding mock data...")
                user1 = models.User(name="Alice", email="alice@example.com", status="active")
                user2 = models.User(name="Bob", email="bob@example.com", status="inactive")
                db.add_all([user1, user2])
                db.commit()
                
                product1 = models.Product(name="Laptop", price=1200.0, stock=10)
                product2 = models.Product(name="Mouse", price=25.0, stock=50)
                db.add_all([product1, product2])
                db.commit()
                
                order1 = models.Order(user_id=user1.id, amount=1225.0)
                db.add(order1)
                db.commit()
                logger.info("Mock data seeded.")
        except Exception as e:
            logger.error(f"Seeding failed: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Startup failed critical: {e}")
