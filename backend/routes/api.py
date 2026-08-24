import logging
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from database.session import get_db, get_engine
from database.manager import db_manager
from database import models
from database.schema_extractor import get_table_schema, get_filtered_tables
from ai_modules.generator import generate_sql_from_text
from ai_modules.verifier import verify_sql_intent
from ai_modules.intent_detector import detect_intent_and_extract_fields
from validators.sql_validator import validate_sql
from validators.sql_detector import is_sql_query
from validators.dialect_validator import validate_dialect_compatibility
from ai_modules.interpreter import interpret_query_result
from ai_modules.followup_generator import generate_followup_questions
from ai_modules.context_analyzer import extract_query_context
from services import insight_service, onboarding_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()



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

class CustomConnectionRequest(BaseModel):
    connection_uri: str
    name: Optional[str] = "Custom Database"

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

@router.get("/databases")
async def get_databases():
    return db_manager.list_databases()

@router.post("/select-database")
async def select_database(request: SelectDatabaseRequest):
    try:
        config = db_manager.set_database(request.db_id)
        models.Base.metadata.create_all(bind=db_manager.engine)
        onboarding_service.run_onboarding(request.db_id)
        return {"success": True, "message": f"Switched to {config['name']}", "db_id": request.db_id}
    except Exception as e:
        logger.error(f"Failed to switch database: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest):
    result = db_manager.test_connection(request.connection_uri)
    return result

@router.post("/connect-custom-db")
async def connect_custom_db(request: CustomConnectionRequest):
    try:
        config = db_manager.set_custom_connection(request.connection_uri, name=request.name)
        models.Base.metadata.create_all(bind=db_manager.engine)
        onboarding_service.run_onboarding(config["id"])
        return {"success": True, "message": f"Connected to {config['name']}", "db_id": config["id"]}
    except Exception as e:
        logger.error(f"Failed to connect custom database: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/database-insights")
async def get_database_insights():
    if not db_manager.current_db_id:
        return {"summary": None, "suggested_queries": [], "tables": []}
    
    insights = onboarding_service.get_onboarding_insights(db_manager.current_db_id)
    if not insights:
        # Try to run it if it doesn't exist
        insights_obj = onboarding_service.run_onboarding(db_manager.current_db_id)
        if insights_obj:
            insights = onboarding_service.get_onboarding_insights(db_manager.current_db_id)
    
    res = insights or {"summary": "No insights available.", "suggested_queries": []}
    if isinstance(res, dict):
        res["tables"] = get_filtered_tables()
    return res

@router.get("/schema/tables")
async def get_schema_tables():
    try:
        tables = get_filtered_tables()
        return {"tables": tables}
    except Exception as e:
        return {"tables": [], "error": str(e)}

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
        dialect = db_manager.engine.name if db_manager.engine else "sqlite"
        sql, intent, is_ambiguous, options = generate_sql_from_text(request.query, dialect=dialect)
        if is_ambiguous:
            return {
                "is_ambiguous": True,
                "intent": intent,
                "options": options,
                "message": f"Ambiguity detected: {intent}. Possible options: {', '.join(options)}"
            }
        return {"sql": sql, "intent": intent, "is_ambiguous": False}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/verify-sql")
async def verify_sql(request: VerifyRequest):
    logger.info(f"--- Stage 2: Verification ---")
    logger.info(f"User Query: {request.query}")
    logger.info(f"Generated SQL: {request.sql}")
    
    result = verify_sql_intent(request.query, request.sql)
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

@router.post("/execute-query")
async def execute_query(request: ExecuteRequest, db: Session = Depends(get_db)):
    logger.info(f"--- Stage 4: Execution ---")
    logger.info(f"SQL for execution: {request.sql}")
    
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

    try:
        result = db.execute(text(request.sql))
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
    logger.info(f"--- CRUD Stage: Intent Detection ---")
    intent_data = detect_intent_and_extract_fields(request.query)
    
    if intent_data.get("error"):
        return {"operation": "ERROR", "error": intent_data["error"]}
    
    operation = intent_data["operation"]
    if operation == "READ":
        return {"operation": "READ"}
    
    table_name = intent_data["table"]
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
async def execute_form(request: CRUDExecuteRequest, db: Session = Depends(get_db)):
    logger.info(f"--- CRUD Stage: Execution ---")
    operation = request.operation.upper()
    table = request.table
    fields = request.fields
    where = request.where or {}

    try:
        if operation == "CREATE":
            cols = ", ".join(fields.keys())
            placeholders = ", ".join([f":{k}" for k in fields.keys()])
            query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
            db.execute(text(query), fields)
            db.commit()
            return {"success": True, "message": f"Successfully created record in {table}."}
        
        elif operation == "UPDATE":
            if not where:
                 return {"success": False, "error": "UPDATE operation requires a WHERE clause for safety."}
            
            set_clause = ", ".join([f"{k} = :val_{k}" for k in fields.keys()])
            where_clause = " AND ".join([f"{k} = :where_{k}" for k in where.keys()])
            
            params = {f"val_{k}": v for k, v in fields.items()}
            params.update({f"where_{k}": v for k, v in where.items()})
            
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            db.execute(text(query), params)
            db.commit()
            return {"success": True, "message": f"Successfully updated record(s) in {table}."}

        elif operation == "DELETE":
            if not where:
                 return {"success": False, "error": "DELETE operation requires a WHERE clause for safety."}
            
            where_clause = " AND ".join([f"{k} = :where_{k}" for k in where.keys()])
            params = {f"where_{k}": v for k, v in where.items()}
            
            query = f"DELETE FROM {table} WHERE {where_clause}"
            db.execute(text(query), params)
            db.commit()
            return {"success": True, "message": f"Successfully deleted record(s) from {table}."}
        
        else:
            return {"success": False, "error": f"Unsupported operation: {operation}"}
            
    except Exception as e:
        logger.error(f"CRUD Execution failed: {e}")
        db.rollback()
        return {"success": False, "error": str(e)}

@router.on_event("startup")
def startup():
    try:
        logger.info("Initializing database...")
        engine = get_engine()
        models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified.")
        
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
