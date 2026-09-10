import os
import json
import logging
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from database import models
from database.schema_extractor import get_filtered_tables, get_filtered_schema
from database.manager import db_manager
from ai_modules.providers import get_llm_provider

logger = logging.getLogger(__name__)


def get_database_stats():
    """
    Computes table count, total record count across non-internal tables, and total foreign key relations.
    Handles empty databases, missing tables, or execution errors gracefully.
    """
    engine = db_manager.engine
    if not engine:
        return {"table_count": 0, "record_count": 0, "relation_count": 0}
    
    try:
        tables = get_filtered_tables(engine)
        if not tables:
            return {"table_count": 0, "record_count": 0, "relation_count": 0}

        inspector = inspect(engine)
        relation_count = 0
        total_records = 0

        # Count foreign key relations
        for t in tables:
            try:
                fks = inspector.get_foreign_keys(t)
                relation_count += len(fks)
            except Exception:
                pass

        # Count rows per table safely
        with engine.connect() as conn:
            for t in tables:
                try:
                    # Quote table name according to dialect
                    quoted_table = engine.dialect.identifier_preparer.quote(t)
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}"))
                    count = res.scalar()
                    if count and isinstance(count, int):
                        total_records += count
                except Exception as row_err:
                    logger.debug(f"Could not count rows for table {t}: {row_err}")

        return {
            "table_count": len(tables),
            "record_count": total_records,
            "relation_count": relation_count
        }
    except Exception as e:
        logger.warning(f"Failed to compute database stats: {e}")
        return {"table_count": 0, "record_count": 0, "relation_count": 0}


def run_onboarding(db_name: str):
    """
    Performs lightweight schema analysis and generates onboarding insights.
    Stores results in HadilDatabaseInsight table.
    """
    logger.info(f"Running onboarding for database: {db_name}")
    
    tables = get_filtered_tables()
    if not tables:
        logger.info(f"Database {db_name} contains no tables. Skipping AI generation.")
        return None

    # 1. Check if insights already exist to avoid redundant AI calls
    db = db_manager.get_session()
    try:
        existing = db.query(models.HadilDatabaseInsight).filter(
            models.HadilDatabaseInsight.database_name == db_name
        ).first()
        if existing:
            logger.info(f"Onboarding already exists for {db_name}. Skipping AI generation.")
            return existing

        # 2. Extract Schema Context
        schema_context = get_filtered_schema()
        
        # 3. AI Prompt for Summary and Suggested Queries
        prompt = f"""
You are a database onboarding assistant for HADIL (AI-assisted database analytics).
Analyze the following database schema and provide:
1. A concise summary (1-2 sentences) of what this database contains (business entities, primary purpose).
2. A list of 6-8 practical, analytics-oriented natural language questions that a user might want to ask this database.

Schema:
{schema_context}

Rules:
- Summary must be lightweight and helpful.
- Suggested questions must be grounded in the actual schema (use existing tables and columns).
- Questions should be diverse (e.g., trend analysis, top performers, status checks).
- Output MUST be a valid JSON object.

JSON Structure:
{{
    "summary": "This database contains...",
    "suggested_queries": [
        "What are the top 5 products by revenue?",
        "Show the monthly sales trend for the last year",
        ...
    ]
}}
"""

        system_prompt = "You are a database expert focused on discoverability and analytics onboarding."
        provider = get_llm_provider("generator")
        result = provider.generate_json(system_prompt, prompt)
        summary = result.get("summary", "No summary available.")
        suggestions = result.get("suggested_queries", [])

        # 4. Save Schema Snapshot to HADIL Metadata DB
        try:
            from database.schema_extractor import extract_schema_snapshot
            from services.metadata_service import metadata_service
            snap = extract_schema_snapshot()
            metadata_service.save_schema_snapshot(db_name, json.dumps(snap))
        except Exception as snap_err:
            logger.warning(f"Could not save metadata schema snapshot: {snap_err}")

        # 5. Store legacy insight table (backwards compatibility)
        insight = models.HadilDatabaseInsight(
            database_name=db_name,
            generated_summary=summary,
            suggested_queries=json.dumps(suggestions),
            generated_at=datetime.datetime.utcnow()
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)
        
        logger.info(f"Onboarding completed for {db_name}")
        return insight

    except Exception as e:
        logger.error(f"Onboarding failed for {db_name}: {e}")
        return None
    finally:
        db.close()

def get_onboarding_insights(db_name: str):
    tables = get_filtered_tables()
    stats = get_database_stats()
    
    if not tables:
        return {
            "database_name": db_name,
            "summary": "No tables discovered in this database.",
            "suggested_queries": [],
            "generated_at": None,
            "stats": stats
        }

    db = db_manager.get_session()
    try:
        if db:
            insight = db.query(models.HadilDatabaseInsight).filter(
                models.HadilDatabaseInsight.database_name == db_name
            ).first()
            if insight:
                return {
                    "database_name": db_name,
                    "summary": insight.generated_summary,
                    "suggested_queries": json.loads(insight.suggested_queries),
                    "generated_at": insight.generated_at,
                    "stats": stats
                }
        return None
    finally:
        if db:
            db.close()
