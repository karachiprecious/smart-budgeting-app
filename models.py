from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class InvalidTransactionError(Exception):
    pass

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100), nullable=True, default="Uncategorized")
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Transaction {self.date} {self.amount} {self.category}>"

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(64))
    amount = db.Column(db.Float)       # <- must exist
    month = db.Column(db.Integer)      # <- must exist
    year = db.Column(db.Integer)       # <- must exist

    def __repr__(self):
        return f"<Budget {self.category} {self.amount} {self.month}/{self.year}>"

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f"<Account {self.name} {self.balance}>"
