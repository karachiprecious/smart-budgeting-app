from collections import defaultdict
from datetime import date
from models import Transaction

def category_summary_for_month(transactions):
    """Return a dict {category: total_amount} for the given transactions."""
    summary = {}
    for t in transactions:
        category = t.category if hasattr(t, 'category') else (t.get('category') if isinstance(t, dict) else 'Uncategorized')
        amount = t.amount if hasattr(t, 'amount') else (t.get('amount') if isinstance(t, dict) else 0)
        summary[category] = summary.get(category, 0) + amount
    return summary


def monthly_total_for_month(transactions):
    """Return total monthly spend or income."""
    return sum((t.amount if hasattr(t, 'amount') else t.get('amount', 0)) for t in transactions)

def filter_transactions_by_month(transactions, year, month):
    """
    Returns transactions filtered by specific year and month
    """
    return [t for t in transactions if t.date.year == year and t.date.month == month]

def sort_transactions_desc(transactions):
    """
    Sorts transactions by date descending
    """
    return sorted(transactions, key=lambda t: t.date, reverse=True)
