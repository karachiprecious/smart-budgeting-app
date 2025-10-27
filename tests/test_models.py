from models import Transaction, InvalidTransactionError
from datetime import date

def test_transaction_init():
    tx = Transaction("2025-10-01", "Food", "Test", -50)
    assert tx.amount == -50.0
    assert tx.category == "Food"
    assert str(tx.date) == "2025-10-01"

def test_transaction_bad_amount():
    try:
        Transaction("2025-10-01", "Food", "bad", "abc")
        assert False, "Should raise InvalidTransactionError"
    except InvalidTransactionError:
        assert True
