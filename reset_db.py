from app.core.database import Base, engine
import app.models.encounter

print("dropping old tables...")
Base.metadata.drop_all(bind=engine)
print("creating fresh tables matching updated models...")
Base.metadata.create_all(bind=engine)
print("database reset complete")