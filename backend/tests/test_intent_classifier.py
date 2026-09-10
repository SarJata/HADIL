import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from validators.intent_classifier import classify_intent, extract_mutation_details
from validators.sql_detector import is_sql_query
from database.manager import db_manager

def test_deterministic_intent_classifier():
    print("\n==========================================")
    print(" RUNNING DETERMINISTIC INTENT CLASSIFIER TESTS")
    print("==========================================")

    import tempfile
    from sqlalchemy import text
    orig_uri = db_manager.custom_connection_uri
    orig_db_id = db_manager.current_db_id
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        db_manager.custom_connection_uri = f"sqlite:///{tmp.name}"
        db_manager.current_db_id = "test_classifier_db.db"
        db_manager._initialize_engine()
        with db_manager.engine.connect() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(255), FirstName VARCHAR(255))"))
            conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, FirstName VARCHAR(255))"))
            conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount FLOAT)"))
            conn.commit()

        # 1. Test SQL detector accuracy on Natural Language vs Raw SQL
        nl_queries = [
            "Create a user Darshan",
            "Create a new customer named Darshan",
            "Add an order for customer 5",
            "Update order 42",
            "Delete order 42",
            "What are the top 5 albums by revenue?"
        ]
        for q in nl_queries:
            assert not is_sql_query(q), f"Natural language query '{q}' falsely detected as raw SQL!"
            print(f"PASS (SQL Detector NL): '{q}' -> is_sql_query=False")

        raw_sql_queries = [
            "SELECT * FROM customers LIMIT 10",
            "CREATE TABLE test_table (id INT)",
            "INSERT INTO customers (FirstName) VALUES ('Darshan')",
            "UPDATE customers SET FirstName='Darshan' WHERE CustomerId=1",
            "DELETE FROM customers WHERE CustomerId=1"
        ]
        for q in raw_sql_queries:
            assert is_sql_query(q), f"Raw SQL query '{q}' failed to be detected as SQL!"
            print(f"PASS (SQL Detector Raw SQL): '{q}' -> is_sql_query=True")

        # 2. Test READ classifications
        read_cases = [
            "show me all orders",
            "how many customers do we have",
            "What are the top 5 albums by revenue?",
            "show customers from India",
            "how do I delete an order",
            "How do I create a user?",
            "Tell me about deleted users.",
            "Can you tell me how to delete an order?",
            "How do I update customer 5?",
            "show me customers who deleted orders",
            "list all products",
            "find artists with more than 10 tracks"
        ]

        for q in read_cases:
            res = classify_intent(q)
            assert res == "READ", f"Failed for query '{q}': expected READ, got {res}"
            print(f"PASS (READ): '{q}' -> {res}")

        # 3. Test Mutation Classifications
        create_cases = [
            "create a new customer",
            "Create a user Darshan",
            "Create a new customer named Darshan",
            "add an order",
            "Add an order for customer 5",
            "insert a new product",
            "Please add a customer named Jata"
        ]

        for q in create_cases:
            res = classify_intent(q)
            assert res == "CREATE", f"Failed for query '{q}': expected CREATE, got {res}"
            print(f"PASS (CREATE): '{q}' -> {res}")

        update_cases = [
            "update order 42",
            "Update order 42",
            "change the price of product 5",
            "modify customer 10",
            "Update customer 5's email to x@example.com."
        ]

        for q in update_cases:
            res = classify_intent(q)
            assert res == "UPDATE", f"Failed for query '{q}': expected UPDATE, got {res}"
            print(f"PASS (UPDATE): '{q}' -> {res}")

        delete_cases = [
            "delete order 42",
            "Delete order 42",
            "remove customer 10",
            "delete all orders",
            "Remove the old orders."
        ]

        for q in delete_cases:
            res = classify_intent(q)
            assert res == "DELETE", f"Failed for query '{q}': expected DELETE, got {res}"
            print(f"PASS (DELETE): '{q}' -> {res}")

        # 4. Deterministic Mutation Field Extraction Regression Suite

        # Case A: "Create a user Darshan"
        ex_a = extract_mutation_details("Create a user Darshan", "CREATE")
        assert ex_a["operation"] == "CREATE"
        assert len(ex_a["fields"]) > 0
        name_extracted = list(ex_a["fields"].values())[0]
        assert name_extracted == "Darshan"
        print(f"PASS Extractor A: 'Create a user Darshan' -> operation='CREATE', fields={ex_a['fields']}")

        # Case B: "Create a new customer named Darshan"
        ex_b = extract_mutation_details("Create a new customer named Darshan", "CREATE")
        assert ex_b["operation"] == "CREATE"
        assert ex_b["table"] == "customers"
        assert ex_b["fields"].get("FirstName") == "Darshan" or "Darshan" in ex_b["fields"].values()
        print(f"PASS Extractor B: 'Create a new customer named Darshan' -> table='customers', fields={ex_b['fields']}")

        # Case C: "Add an order for Jata worth 1500"
        ex_c = extract_mutation_details("Add an order for Jata worth 1500", "CREATE")
        assert ex_c["operation"] == "CREATE"
        assert "invoices" in ex_c["table"] or "orders" in ex_c["table"] or "customers" in ex_c["table"]
        assert 1500 in ex_c["fields"].values() or 1500.0 in ex_c["fields"].values()
        print(f"PASS Extractor C: 'Add an order for Jata worth 1500' -> fields={ex_c['fields']}")

        # Case D: "Update order 42 and change amount to 1500"
        ex_d = extract_mutation_details("Update order 42 and change amount to 1500", "UPDATE")
        assert ex_d["operation"] == "UPDATE"
        assert 42 in ex_d["where"].values()
        assert 1500 in ex_d["fields"].values() or 1500.0 in ex_d["fields"].values()
        print(f"PASS Extractor D: 'Update order 42 and change amount to 1500' -> where={ex_d['where']}, fields={ex_d['fields']}")

        # Case E: "Delete order 42"
        ex_e = extract_mutation_details("Delete order 42", "DELETE")
        assert ex_e["operation"] == "DELETE"
        assert 42 in ex_e["where"].values()
        print(f"PASS Extractor E: 'Delete order 42' -> where={ex_e['where']}")

        # Case F: "Create a user with id 1234"
        ex_f = extract_mutation_details("Create a user with id 1234", "CREATE")
        assert ex_f["operation"] == "CREATE"
        assert ex_f["table"] == "users"
        assert 1234 in ex_f["fields"].values()
        assert len(ex_f["where"]) == 0
        print(f"PASS Extractor F: 'Create a user with id 1234' -> table='users', fields={ex_f['fields']}, where={ex_f['where']}")

        # Case G: "Create a user with ID 9999"
        ex_g = extract_mutation_details("Create a user with ID 9999", "CREATE")
        assert ex_g["operation"] == "CREATE"
        assert 9999 in ex_g["fields"].values()
        assert len(ex_g["where"]) == 0
        print(f"PASS Extractor G: 'Create a user with ID 9999' -> fields={ex_g['fields']}")

        # Case H: "Create user #5678"
        ex_h = extract_mutation_details("Create user #5678", "CREATE")
        assert ex_h["operation"] == "CREATE"
        assert 5678 in ex_h["fields"].values()
        assert len(ex_h["where"]) == 0
        print(f"PASS Extractor H: 'Create user #5678' -> fields={ex_h['fields']}")

        # 5. Table Creation vs Record Creation Routing Suite (Exact Requirements)
        table_creation_queries = [
            ("Create table user", "user"),
            ("Create a table user", "user"),
            ("Create a table called user", "user"),
            ("Create a table named user", "user"),
            ("Add table user", "user"),
            ("Add a table user", "user"),
            ("Add a table called user", "user"),
            ("Make a new table user", "user"),
            ("Make a new table called user", "user"),
            ("Create a new table named user", "user"),
        ]
        for q, expected_name in table_creation_queries:
            res_op = classify_intent(q)
            assert res_op == "CREATE_TABLE", f"Failed for table creation query '{q}': expected CREATE_TABLE, got {res_op}"
            from validators.intent_classifier import detect_table_creation_intent
            info = detect_table_creation_intent(q)
            assert info is not None, f"Failed detect_table_creation_intent for '{q}'"
            assert info["table_name"] == expected_name, f"Expected table_name '{expected_name}', got '{info['table_name']}'"
            print(f"PASS (CREATE_TABLE): '{q}' -> operation='CREATE_TABLE', table_name='{info['table_name']}'")

        record_creation_queries = [
            "Create a user",
            "Create a user record",
            "Add a user",
            "Add an inventory item",
            "Add a product",
            "Create an inventory record"
        ]
        for q in record_creation_queries:
            res_op = classify_intent(q)
            assert res_op == "CREATE", f"Failed for record creation query '{q}': expected CREATE, got {res_op}"
            print(f"PASS (Record CREATE): '{q}' -> operation='CREATE'")

        # 6. Schema / Metadata Routing Suite
        schema_queries = [
            "How many tables does my database have?",
            "what tables are in my database?",
            "how many relationships exist?",
            "what columns does orders have?"
        ]
        for q in schema_queries:
            res_op = classify_intent(q)
            assert res_op == "SCHEMA_METADATA", f"Failed for schema query '{q}': expected SCHEMA_METADATA, got {res_op}"
            print(f"PASS (SCHEMA_METADATA): '{q}' -> operation='SCHEMA_METADATA'")

        print("\n--- ALL DETERMINISTIC INTENT CLASSIFIER & FIELD EXTRACTION TESTS PASSED SUCCESSFULLY! ---")
    finally:
        db_manager.custom_connection_uri = orig_uri
        db_manager.current_db_id = orig_db_id
        db_manager._initialize_engine()
        try:
            os.remove(tmp.name)
        except Exception:
            pass

if __name__ == "__main__":
    test_deterministic_intent_classifier()
