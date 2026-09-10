import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.manager import DatabaseManager
from services.onboarding_service import get_onboarding_insights, get_database_stats, run_onboarding
from database.metadata_db import metadata_manager, MetadataBase
from database.models import Base, HadilDatabaseInsight

class TestDatabaseSwitchIsolation(unittest.TestCase):

    def setUp(self):
        MetadataBase.metadata.create_all(bind=metadata_manager.engine)
        Base.metadata.create_all(bind=metadata_manager.engine)
        self.db_manager = DatabaseManager()

    def test_01_switch_populated_a_to_empty_b_and_back_to_a(self):
        """
        Covers Requirements 1-7:
        1. Database A has 14 tables / 3,484 records.
        2. Database B is empty.
        3. Switch A -> B.
        4. Verify dashboard statistics for B are: tables = 0, records = 0.
        5. Verify A's 14 / 3,484 values are not returned for B.
        6. Switch B -> A.
        7. Verify A's statistics return correctly.
        """
        db_a_id = "populated_db_a"
        db_b_id = "empty_db_b"

        session = metadata_manager.get_session()
        try:
            session.query(HadilDatabaseInsight).filter(
                HadilDatabaseInsight.database_name.in_([db_a_id, db_b_id])
            ).delete(synchronize_session=False)

            insight_a = HadilDatabaseInsight(
                database_name=db_a_id,
                generated_summary="Populated database with 14 tables.",
                suggested_queries='["Select top items"]'
            )
            session.add(insight_a)
            session.commit()
        finally:
            session.close()

        # --- STEP 1: Connect to Database A ---
        self.db_manager.current_db_id = db_a_id
        with patch("services.onboarding_service.get_filtered_tables", return_value=[f"table_{i}" for i in range(14)]), \
             patch("services.onboarding_service.get_database_stats", return_value={"table_count": 14, "record_count": 3484, "relation_count": 82}), \
             patch("services.onboarding_service.db_manager.get_session", side_effect=metadata_manager.get_session):
            
            stats_a = get_onboarding_insights(db_a_id)
            self.assertEqual(stats_a["stats"]["table_count"], 14)
            self.assertEqual(stats_a["stats"]["record_count"], 3484)

        # --- STEP 2 & 3: Switch A -> B (Empty DB B) ---
        self.db_manager.current_db_id = db_b_id
        with patch("services.onboarding_service.get_filtered_tables", return_value=[]), \
             patch("services.onboarding_service.get_database_stats", return_value={"table_count": 0, "record_count": 0, "relation_count": 0}):

            stats_b = get_onboarding_insights(db_b_id)
            
            # --- STEP 4 & 5: Verify B statistics are 0 and A's 14/3,484 are NOT returned ---
            self.assertEqual(stats_b["stats"]["table_count"], 0)
            self.assertEqual(stats_b["stats"]["record_count"], 0)
            self.assertEqual(stats_b["stats"]["relation_count"], 0)
            self.assertNotEqual(stats_b["stats"]["table_count"], 14)
            self.assertNotEqual(stats_b["stats"]["record_count"], 3484)

        # --- STEP 6 & 7: Switch B -> A ---
        self.db_manager.current_db_id = db_a_id
        with patch("services.onboarding_service.get_filtered_tables", return_value=[f"table_{i}" for i in range(14)]), \
             patch("services.onboarding_service.get_database_stats", return_value={"table_count": 14, "record_count": 3484, "relation_count": 82}), \
             patch("services.onboarding_service.db_manager.get_session", side_effect=metadata_manager.get_session):

            stats_a_returned = get_onboarding_insights(db_a_id)
            self.assertEqual(stats_a_returned["stats"]["table_count"], 14)
            self.assertEqual(stats_a_returned["stats"]["record_count"], 3484)

    def test_02_remote_database_statistics_scoped_correctly(self):
        """Covers Requirement 8: Remote database statistics are scoped correctly."""
        remote_mysql_id = "remote_mysql_analytics"
        self.db_manager.current_db_id = remote_mysql_id
        
        session = metadata_manager.get_session()
        try:
            session.query(HadilDatabaseInsight).filter(
                HadilDatabaseInsight.database_name == remote_mysql_id
            ).delete(synchronize_session=False)

            insight_remote = HadilDatabaseInsight(
                database_name=remote_mysql_id,
                generated_summary="Remote analytics DB.",
                suggested_queries='[]'
            )
            session.add(insight_remote)
            session.commit()
        finally:
            session.close()

        with patch("services.onboarding_service.get_filtered_tables", return_value=["orders", "products"]), \
             patch("services.onboarding_service.get_database_stats", return_value={"table_count": 2, "record_count": 150, "relation_count": 1}), \
             patch("services.onboarding_service.db_manager.get_session", side_effect=metadata_manager.get_session):

            insights = get_onboarding_insights(remote_mysql_id)
            self.assertIsNotNone(insights)
            self.assertEqual(insights["database_name"], remote_mysql_id)
            self.assertEqual(insights["stats"]["table_count"], 2)
            self.assertEqual(insights["stats"]["record_count"], 150)

    def test_03_empty_database_does_not_invoke_llm(self):
        """Covers Requirement: Empty database skips LLM API call entirely."""
        with patch("services.onboarding_service.get_filtered_tables", return_value=[]), \
             patch("services.onboarding_service.get_llm_provider") as mock_llm:
            
            result = run_onboarding("empty_remote_mysql")
            self.assertIsNone(result)
            mock_llm.assert_not_called()

if __name__ == "__main__":
    unittest.main()
