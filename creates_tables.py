from app.core.database import engine, Base
import app.models

if __name__ == "__main__":
    print("creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("tables created successfully.")