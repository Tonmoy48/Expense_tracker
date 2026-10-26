from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from database import Base
from main import app
from router.auth import get_db, get_current_user
from models import User

SQLALCHEMY_TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(
            User.username == "test_user"
        ).first()

        if user is None:
            user = User(
                username="test_user",
                email="test_user@example.com",
                hashed_password="not_used_for_these_tests",
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


def test_create_transaction():
    response = client.post(
        "/transactions/",
        json={
            "title": "Test Grocery",
            "amount": 500,
            "type": "expense",
            "category": "Food",
            "date": "2026-10-26",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["title"] == "Test Grocery"
    assert data["amount"] == 500
    assert data["type"] == "expense"
    assert data["category"] == "Food"
    assert data["date"] == "2026-10-26"
    assert data["owner_id"] is not None


def test_get_transactions():
    response = client.get("/transactions/")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(
        transaction["title"] == "Test Grocery"
        for transaction in data
    )


def test_get_specific_transaction():
    create_response = client.post(
        "/transactions/",
        json={
            "title": "Specific Test Transaction",
            "amount": 750,
            "type": "expense",
            "category": "Transport",
            "date": "2026-10-26",
        },
    )

    assert create_response.status_code == 201

    transaction_id = create_response.json()["id"]

    response = client.get(f"/transactions/{transaction_id}")

    assert response.status_code == 200
    assert response.json()["id"] == transaction_id
    assert response.json()["title"] == "Specific Test Transaction"


def test_update_transaction():
    create_response = client.post(
        "/transactions/",
        json={
            "title": "Old Title",
            "amount": 500,
            "type": "expense",
            "category": "Food",
            "date": "2026-10-26",
        },
    )

    assert create_response.status_code == 201

    transaction_id = create_response.json()["id"]

    update_response = client.put(
        f"/transactions/{transaction_id}",
        json={
            "title": "Updated Title",
            "amount": 800,
            "type": "expense",
            "category": "Transport",
            "date": "2026-10-26",
        },
    )

    assert update_response.status_code == 200

    data = update_response.json()

    assert data["title"] == "Updated Title"
    assert data["amount"] == 800
    assert data["category"] == "Transport"


def test_delete_transaction():
    create_response = client.post(
        "/transactions/",
        json={
            "title": "Transaction to Delete",
            "amount": 300,
            "type": "expense",
            "category": "Shopping",
            "date": "2026-10-26",
        },
    )

    assert create_response.status_code == 201

    transaction_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/transactions/{transaction_id}"
    )

    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == (
        "Transaction deleted successfully"
    )

    get_response = client.get(
        f"/transactions/{transaction_id}"
    )

    assert get_response.status_code == 404


def test_filter_transactions():
    client.post(
        "/transactions/",
        json={
            "title": "Filter Test Income",
            "amount": 5000,
            "type": "income",
            "category": "Freelance",
            "date": "2026-10-26",
        },
    )

    response = client.get(
        "/transactions/filter",
        params={
            "type": "income",
            "category": "Freelance",
            "minimum_amount": 1000,
            "maximum_amount": 6000,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) >= 1
    assert all(item["type"] == "income" for item in data)
    assert all(item["category"] == "Freelance" for item in data)
    assert all(
        1000 <= item["amount"] <= 6000
        for item in data
    )


def test_get_nonexistent_transaction():
    response = client.get("/transactions/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"


def test_create_transaction_with_negative_amount():
    response = client.post(
        "/transactions/",
        json={
            "title": "Invalid Transaction",
            "amount": -100,
            "type": "expense",
            "category": "Food",
            "date": "2026-10-26",
        },
    )

    assert response.status_code == 422


def test_create_transaction_with_invalid_type():
    response = client.post(
        "/transactions/",
        json={
            "title": "Invalid Type Transaction",
            "amount": 500,
            "type": "saving",
            "category": "Other",
            "date": "2026-10-26",
        },
    )

    assert response.status_code == 422
