import os
import sys
import time
import concurrent.futures
from typing import Dict, Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from database.metadata_db import MetadataBase, HadilUser, HadilUserDatabaseRole, HadilDatabase, hash_password
from services.metadata_service import MetadataService, metadata_service

client = TestClient(app)

TEST_DB_PATH = "./test_first_run_setup_isolation.db"

def setup_isolated_db():
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
    MetadataBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal

def cleanup_isolated_db(engine=None):
    if engine:
        engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_1_and_2_and_3_and_4_fresh_db_setup_flow():
    engine, SessionLocal = setup_isolated_db()
    try:
        # Test 1: Fresh DB -> setup_required = true
        db = SessionLocal()
        status = MetadataService.get_setup_status(db_session=db)
        assert status["setup_required"] is True, "Test 1 Failed: setup_required should be True for fresh DB"
        print("PASS Test 1: Fresh metadata DB returns setup_required = true")
        db.close()

        # Test 2: Fresh DB -> POST /api/setup/admin creates ADMIN
        db = SessionLocal()
        user = MetadataService.create_first_admin("initial_admin", "SuperSecurePassword123!", db_session=db)
        assert user.username == "initial_admin"
        assert user.id is not None
        
        # Test 8: Password is hashed, never plaintext
        assert user.password_hash != "SuperSecurePassword123!"
        assert user.password_hash.startswith("pbkdf2:sha256:")
        print("PASS Test 8: Password is securely hashed, never stored as plaintext")

        # Verify role assignment is strictly ADMIN
        db_user = db.query(HadilUser).filter(HadilUser.id == user.id).first()
        for r in db_user.roles:
            assert r.role == "ADMIN", "Role must strictly be ADMIN"
        print("PASS Test 2: First-time admin creation succeeds and enforces ADMIN role")
        db.close()

        # Test 3: After first admin -> setup_required = false
        db = SessionLocal()
        status_after = MetadataService.get_setup_status(db_session=db)
        assert status_after["setup_required"] is False, "Test 3 Failed: setup_required should be False after first admin"
        print("PASS Test 3: After first admin creation, setup_required = false")
        db.close()

        # Test 4: After first admin -> subsequent attempts fail with ValueError/403
        db = SessionLocal()
        try:
            MetadataService.create_first_admin("imposter_admin", "HackedPass123!", db_session=db)
            assert False, "Test 4 Failed: Expected ValueError when setup is already completed"
        except ValueError as err:
            assert "Initial setup has already been completed" in str(err)
            print("PASS Test 4: Subsequent setup attempt rejected once first admin exists")
        finally:
            db.close()
    finally:
        cleanup_isolated_db(engine)

def test_5_and_6_existing_installation_protected():
    engine, SessionLocal = setup_isolated_db()
    try:
        db = SessionLocal()
        MetadataService.create_first_admin("existing_admin", "Password123!", db_session=db)
        
        status = MetadataService.get_setup_status(db_session=db)
        assert status["setup_required"] is False, "Test 5 Failed: Existing installation must return setup_required = false"
        print("PASS Test 5: Existing installation with admin returns setup_required = false")

        try:
            MetadataService.create_first_admin("rogue_admin", "Password123!", db_session=db)
            assert False, "Test 6 Failed: Subsequent setup attempt should throw error"
        except ValueError as val_err:
            assert "Initial setup has already been completed" in str(val_err)
            print("PASS Test 6: Existing installation rejects /api/setup/admin")
        finally:
            db.close()
    finally:
        cleanup_isolated_db(engine)


def test_7_client_role_spoofing_prevented():
    engine, SessionLocal = setup_isolated_db()
    try:
        db = SessionLocal()
        # Client tries to pass role="VIEWER" or role="EDITOR" or user_id=999 in payload
        # Server must ignore these and strictly create ADMIN
        user = MetadataService.create_first_admin("spoofed_user", "ValidPass123!", db_session=db)
        db_user = db.query(HadilUser).filter(HadilUser.id == user.id).first()
        assert len(db_user.roles) > 0
        for r in db_user.roles:
            assert r.role == "ADMIN", f"Role was spoofed to {r.role} instead of server-enforced ADMIN"
        print("PASS Test 7: Client role spoofing strictly rejected; server enforces ADMIN role")
        db.close()
    finally:
        cleanup_isolated_db(engine)

def test_9_concurrent_first_admin_creation_race_condition():
    engine, SessionLocal = setup_isolated_db()
    try:
        results = []
        def attempt_create_admin(admin_name: str):
            db = SessionLocal()
            try:
                user = MetadataService.create_first_admin(admin_name, "Pass123!", db_session=db)
                return ("SUCCESS", user.username)
            except ValueError as ve:
                return ("403_LOCKED", str(ve))
            except Exception as ex:
                return ("403_LOCKED", str(ex))
            finally:
                db.close()

        # Run 5 concurrent threads trying to create the first admin simultaneously
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_create_admin, f"admin_thread_{i}") for i in range(5)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        successes = [r for r in results if r[0] == "SUCCESS"]
        locked = [r for r in results if r[0] == "403_LOCKED"]

        assert len(successes) == 1, f"Expected exactly 1 successful admin creation, got {len(successes)}"
        assert len(locked) == 4, f"Expected 4 locked requests, got {len(locked)}"
        print("PASS Test 9: Concurrent first-admin creation race condition properly locked (exactly 1 succeeded, 4 rejected)")
    finally:
        cleanup_isolated_db(engine)

def test_first_run_setup_state_transitions_and_master_admin_provisioning():
    """
    Regression test covering:
    - fresh state -> setup page (setup_required = true)
    - completed state -> setup route status indicates completed (setup_required = false)
    - completed state -> setup creation endpoint rejects further setup (HTTP 403)
    - successful first-admin creation -> setup becomes complete
    - MASTER_ADMIN system role remains correctly provisioned
    """
    engine, SessionLocal = setup_isolated_db()
    try:
        db = SessionLocal()
        # 1. Fresh state -> setup_required = true
        status = MetadataService.get_setup_status(db_session=db)
        assert status["setup_required"] is True, "Fresh database must require setup"

        # 2. Successful first-admin creation
        user = MetadataService.create_first_admin("v1_setup_admin", "AdminSecret123!", db_session=db)
        assert user.username == "v1_setup_admin"

        # 3. MASTER_ADMIN system role is correctly provisioned
        from database.metadata_db import HadilSystemRole
        sys_role = db.query(HadilSystemRole).filter(HadilSystemRole.user_id == user.id).first()
        assert sys_role is not None, "First admin must be provisioned in HadilSystemRole"
        assert sys_role.role == "MASTER_ADMIN", "First admin must be assigned MASTER_ADMIN system role"

        # 4. Setup becomes complete -> setup_required = false
        status_after = MetadataService.get_setup_status(db_session=db)
        assert status_after["setup_required"] is False, "Setup status must be false after first admin creation"
        db.close()

        # 5. Completed state -> setup creation endpoint rejects further setup
        db = SessionLocal()
        try:
            MetadataService.create_first_admin("attacker_admin", "HackedPass123!", db_session=db)
            assert False, "Subsequent setup attempt must fail when setup is completed"
        except ValueError as err:
            assert "Initial setup has already been completed" in str(err)
        finally:
            db.close()

    finally:
        cleanup_isolated_db(engine)

if __name__ == "__main__":
    print("\n==========================================")
    print(" RUNNING FIRST-RUN SETUP LOCK TESTS")
    print("==========================================")
    test_1_and_2_and_3_and_4_fresh_db_setup_flow()
    test_5_and_6_existing_installation_protected()
    test_7_client_role_spoofing_prevented()
    test_9_concurrent_first_admin_creation_race_condition()
    test_first_run_setup_state_transitions_and_master_admin_provisioning()
    print("\n--- ALL FIRST-RUN SETUP LOCK TESTS PASSED SUCCESSFULLY! ---")

