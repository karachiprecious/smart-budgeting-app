from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Transaction, Budget, InvalidTransactionError
from importer import import_csv_file_from_path_or_file
from utils import category_summary_for_month, monthly_total_for_month
from datetime import datetime
import os

app = Flask(__name__, template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///budget.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "dev-secret-key"

db.init_app(app)
with app.app_context():
    db.create_all()

# -----------------------------
# Dashboard
# -----------------------------
@app.route("/")
@app.route("/")
def dashboard():
    now = datetime.now()
    year = now.year
    month = now.month

    # Fetch all transactions
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()

    # Transactions for this month
    monthly_transactions = [t for t in transactions if t.date.year == year and t.date.month == month]
    category_data = category_summary_for_month(monthly_transactions)
    total_balance = sum(t.amount for t in transactions)
    monthly_total = monthly_total_for_month(monthly_transactions)

    # Remaining budgets
    budgets = Budget.query.filter_by(month=month, year=year).all()
    remaining_budget = {}
    for b in budgets:
        spent = sum(t.amount for t in monthly_transactions if t.category == b.category)
        remaining_budget[b.category] = b.amount - spent

    # ---- NEW: Compute Monthly Totals for Bar Chart ----
    from collections import defaultdict
    monthly_data = defaultdict(float)
    for t in transactions:
        month_name = t.date.strftime("%b %Y")
        monthly_data[month_name] += t.amount

    # Sort by date (latest last)
    monthly_data = dict(sorted(monthly_data.items(), key=lambda x: datetime.strptime(x[0], "%b %Y")))

    # Limit to last 6 months for clarity
    if len(monthly_data) > 6:
        monthly_data = dict(list(monthly_data.items())[-6:])

    return render_template(
        "dashboard.html",
        transactions=monthly_transactions,
        category_data=category_data,
        total_balance=total_balance,
        monthly_total=monthly_total,
        remaining_budget=remaining_budget,
        monthly_data=monthly_data  # ✅ Added
    )

# -----------------------------
# View all transactions
# -----------------------------
@app.route("/transactions")
def list_transactions():
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return render_template("transactions.html", transactions=transactions)

# -----------------------------
# Add transaction
# -----------------------------
@app.route("/add", methods=["GET", "POST"])
def add_transaction():
    if request.method == "POST":
        try:
            date_str = request.form.get("date")
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            category = request.form.get("category") or "Uncategorized"
            description = request.form.get("description") or ""
            amount = float(request.form.get("amount"))
            tx = Transaction(date=tx_date, category=category, description=description, amount=amount)
            db.session.add(tx)
            db.session.commit()
            flash("Transaction added.", "success")
            return redirect(url_for("list_transactions"))
        except (ValueError, InvalidTransactionError) as e:
            flash(f"Error: {e}", "danger")
            return redirect(url_for("add_transaction"))
    return render_template("add_transaction.html")

# -----------------------------
# Edit transaction
# -----------------------------
@app.route("/edit/<int:tx_id>", methods=["GET", "POST"])
def edit_transaction(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if request.method == "POST":
        try:
            tx.date = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()
            tx.category = request.form.get("category") or "Uncategorized"
            tx.description = request.form.get("description") or ""
            tx.amount = float(request.form.get("amount"))
            db.session.commit()
            flash("Transaction updated.", "success")
            return redirect(url_for("list_transactions"))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")
            return redirect(url_for("edit_transaction", tx_id=tx_id))
    return render_template("edit_transaction.html", transaction=tx)

# -----------------------------
# Delete transaction
# -----------------------------
@app.route("/delete/<int:tx_id>", methods=["POST"])
def delete_transaction(tx_id):
    txn = Transaction.query.get_or_404(tx_id)
    db.session.delete(txn)
    db.session.commit()
    flash("Transaction deleted successfully!", "success")
    return redirect(url_for("list_transactions"))

# -----------------------------
# Import CSV
# -----------------------------
@app.route("/import", methods=["GET", "POST"])
def import_file():
    if request.method == "POST":
        if "file" not in request.files or request.files["file"].filename == "":
            flash("No file selected", "danger")
            return redirect(request.url)

        file = request.files["file"]
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        tmp_path = os.path.join(uploads_dir, file.filename)
        file.save(tmp_path)

        try:
            imported = import_csv_file_from_path_or_file(tmp_path)
            added = 0
            for item in imported:
                d = item.get("date")
                if isinstance(d, str):
                    d = datetime.strptime(d, "%Y-%m-%d").date()
                tx = Transaction(
                    date=d,
                    category=item.get("category") or "Uncategorized",
                    description=item.get("description") or "",
                    amount=float(item.get("amount") or 0)
                )
                db.session.add(tx)
                added += 1
            db.session.commit()
            flash(f"Imported {added} transactions.", "success")
        except Exception as e:
            flash(f"Import failed: {e}", "danger")
        finally:
            os.remove(tmp_path)

        return redirect(url_for("dashboard"))

    return render_template("import.html")


@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        for cat in categories:
            value = request.form.get(f"budget_{cat.id}")
            try:
                cat.budget = float(value or 0)
            except:
                cat.budget = 0
        db.session.commit()
        flash("Budgets updated.", "success")
        return redirect(url_for("budgets"))
    return render_template("budget.html", categories=categories)


# -----------------------------
# Add/Update Budgets
# -----------------------------
@app.route("/budget", methods=["GET", "POST"])
def manage_budget():
    now = datetime.now()
    year, month = now.year, now.month
    if request.method == "POST":
        category = request.form.get("category")
        amount = float(request.form.get("amount"))
        budget = Budget.query.filter_by(category=category, month=month, year=year).first()
        if not budget:
            budget = Budget(category=category, month=month, year=year, amount=amount)
            db.session.add(budget)
        else:
            budget.amount = amount
        db.session.commit()
        flash("Budget saved.", "success")
        return redirect(url_for("dashboard"))

    budgets = Budget.query.filter_by(month=month, year=year).all()
    return render_template("budget.html", budgets=budgets)

# -----------------------------
# Admin: clear all transactions (for testing)
# -----------------------------
@app.route("/admin/clear", methods=["POST"])
def admin_clear():
    num = Transaction.query.delete()
    db.session.commit()
    flash(f"Cleared {num} transactions.", "info")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
