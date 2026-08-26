import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base, Merchant, Product


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    merchant = Merchant(name="Test Merchant")
    session.add(merchant)
    session.commit()
    session.refresh(merchant)

    session.add(Product(merchant_id=merchant.id, name="Test Widget", description="a widget for testing", category="test", price=500, stock=10))
    session.commit()

    yield session
    session.close()
