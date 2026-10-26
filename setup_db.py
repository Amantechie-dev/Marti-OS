import psycopg2

try:
    # Update "your_password" to whatever you set during Postgres installation
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="Aman$1ngh",
        host="127.0.0.1",
        port="5432"
    )
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS triage_results (
            id SERIAL PRIMARY KEY,
            patient_id VARCHAR(50),
            risk_score INT,
            status VARCHAR(20)
        );
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Success: Table created!")
    
except Exception as e:
    print(f"Error connecting to PostgreSQL: {e}")
