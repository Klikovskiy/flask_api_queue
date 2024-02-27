from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

TASK_CHECK_INTERVAL_MINUTES = 10
DATABASE_URL = "postgresql://postgres:root@localhost/flask_base2"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()
