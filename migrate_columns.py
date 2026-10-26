from sqlalchemy import text
from app.core.database import engine

def migrate():
    statements = [
        "ALTER TABLE encounters ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE encounters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE intake_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE triage_results ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE approval_records ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
        "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    print("migration complete: missing columns added successfully")

if __name__ == "__main__":
    migrate()