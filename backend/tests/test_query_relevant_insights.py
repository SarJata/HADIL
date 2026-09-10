import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.insight_service import generate_insights

def test_query_relevant_insights_suite():
    print("\n==========================================")
    print(" RUNNING QUERY-RELEVANT INSIGHTS SUITE")
    print("==========================================")

    # 1. "Show me all users" -> no generic statistical insights
    users_data = [
        {"id": 1, "name": "Alice", "status": "active"},
        {"id": 2, "name": "Bob", "status": "inactive"}
    ]
    res_1 = generate_insights(users_data, query="Show me all users", sql="SELECT * FROM users;")
    assert res_1 == [], f"Expected [], got {res_1}"
    print(f"PASS Test 1: 'Show me all users' -> {res_1}")

    # 2. "How many customers are from each country?" -> country/customer-count insight generated
    country_data = [
        {"Country": "USA", "num_customers": 13},
        {"Country": "Canada", "num_customers": 8},
        {"Country": "France", "num_customers": 5}
    ]
    res_2 = generate_insights(country_data, query="How many customers are from each country?", sql="SELECT Country, COUNT(*) as num_customers FROM customers GROUP BY Country;")
    assert len(res_2) == 1
    assert "USA" in res_2[0]
    print(f"PASS Test 2: 'How many customers are from each country?' -> {res_2}")

    # 3. "What are the top 5 albums by revenue?" -> revenue/ranking insight generated
    albums_data = [
        {"Title": "Greatest Hits", "Total": 1500.50},
        {"Title": "Album B", "Total": 1200.00},
        {"Title": "Album C", "Total": 900.00}
    ]
    res_3 = generate_insights(albums_data, query="What are the top 5 albums by revenue?", sql="SELECT Title, SUM(Total) as Total FROM albums GROUP BY Title ORDER BY Total DESC LIMIT 5;")
    assert len(res_3) == 1
    assert "Greatest Hits" in res_3[0] and "$1,500.50" in res_3[0]
    print(f"PASS Test 3: 'What are the top 5 albums by revenue?' -> {res_3}")

    # 4. "Show me customers" -> no arbitrary ID/name/email statistics
    cust_data = [
        {"CustomerId": 1, "FirstName": "John", "Email": "john@example.com"},
        {"CustomerId": 2, "FirstName": "Jane", "Email": "jane@example.com"}
    ]
    res_4 = generate_insights(cust_data, query="Show me customers", sql="SELECT * FROM customers;")
    assert res_4 == [], f"Expected [], got {res_4}"
    print(f"PASS Test 4: 'Show me customers' -> {res_4}")

    # 5. "What is the average order value?" -> average order value is relevant
    order_data = [
        {"order_id": 1, "amount": 100.00},
        {"order_id": 2, "amount": 200.00},
        {"order_id": 3, "amount": 300.00}
    ]
    res_5 = generate_insights(order_data, query="What is the average order value?", sql="SELECT AVG(amount) as amount FROM orders;")
    assert len(res_5) == 1
    assert "$200.00" in res_5[0]
    print(f"PASS Test 5: 'What is the average order value?' -> {res_5}")

    # 6. Two-row dataset (Alice, Bob) -> must NOT produce "Alice is the most frequent name."
    alice_bob_data = [
        {"name": "Alice"},
        {"name": "Bob"}
    ]
    res_6 = generate_insights(alice_bob_data, query="Show me users", sql="SELECT name FROM users;")
    assert "Alice is the most frequent name" not in str(res_6)
    assert res_6 == []
    print(f"PASS Test 6: Two-row dataset for 'Show me users' -> {res_6}")

    # 7. Dataset with IDs 1 and 2 -> must NOT produce "The average ID is 1.50"
    id_data = [
        {"id": 1, "name": "A"},
        {"id": 2, "name": "B"}
    ]
    res_7 = generate_insights(id_data, query="Show me users", sql="SELECT id, name FROM users;")
    assert "average ID" not in str(res_7)
    assert res_7 == []
    print(f"PASS Test 7: Dataset with IDs 1 and 2 -> {res_7}")

    # 8. Empty result set -> no insights
    res_8 = generate_insights([], query="Show me users", sql="SELECT * FROM users;")
    assert res_8 == []
    print(f"PASS Test 8: Empty result set -> {res_8}")

    # 9. Large result set -> do not generate a large number of generic takeaways
    large_data = [{"id": i, "val": i * 10, "cat": f"Cat_{i % 5}"} for i in range(100)]
    res_9 = generate_insights(large_data, query="Show me all rows", sql="SELECT * FROM data;")
    assert res_9 == []
    print(f"PASS Test 9: Large generic result set -> {res_9}")

    print("\n--- ALL QUERY-RELEVANT INSIGHTS SUITE TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    test_query_relevant_insights_suite()
