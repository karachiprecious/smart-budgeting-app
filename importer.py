import csv
import re
from datetime import datetime
from typing import List, Dict
from models import db, Transaction

# ==========================
# COMMON PATTERNS
# ==========================
COMMON_PATTERNS = [
    # YYYY-MM-DD, amount, description
    re.compile(r'(?P<date>\d{4}-\d{2}-\d{2})\s*[,;]\s*(?P<amount>-?\d+[\.,]?\d*)\s*[,;]\s*(?P<desc>.+)'),
    # DD/MM/YYYY | amount | desc
    re.compile(r'(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s*\|\s*(?P<amount>-?\d+[\.,]?\d*)\s*\|\s*(?P<desc>.+)'),
    # generic: date ... DR/CR ... amount ...
    re.compile(r'(?P<date>\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(?P<desc>.*?)\s+(?P<drcr>DR|CR)?\s*(?P<amount>\d+[\.,]?\d*)'),
]

# ==========================
# DATE PARSING
# ==========================
def try_parse_date(s: str):
    """Attempts multiple date formats."""
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Unrecognized date format: {s}")


# ==========================
# NORMALIZE SINGLE LINE
# ==========================
def normalize_row_text(line: str) -> Dict:
    """Try to extract date, amount, and description from a messy text line."""
    for pat in COMMON_PATTERNS:
        m = pat.search(line)
        if m:
            gd = m.groupdict()
            raw_date = gd.get('date')
            try:
                date = try_parse_date(raw_date) if raw_date else None
            except Exception:
                date = None
            raw_amount = gd.get('amount') or "0"
            raw_amount = raw_amount.replace(",", "")
            amount = float(raw_amount)
            if 'drcr' in gd and gd.get('drcr') and gd['drcr'].upper() == 'DR':
                amount = -abs(amount)
            description = gd.get('desc') or ""
            return {
                'date': date,
                'amount': amount,
                'description': description.strip(),
                'category': None
            }

    # fallback: simple split by comma/semicolon
    parts = [p.strip() for p in re.split(r',|;', line) if p.strip()]
    if len(parts) >= 3:
        try:
            date = try_parse_date(parts[0])
            amount = float(parts[1].replace(',', ''))
            desc = " ".join(parts[2:])
            return {'date': date, 'amount': amount, 'description': desc, 'category': None}
        except Exception:
            pass

    raise ValueError(f"Could not normalize: {line}")


# ==========================
# IMPORT CSV FILE
# ==========================
def import_csv_file_from_path_or_file(path_or_file) -> List[Transaction]:
    """
    Reads a CSV file (path or uploaded file), normalizes the data, 
    and saves transactions to the database.
    """
    transactions = []

    # Try using pandas for well-structured CSVs
    try:
        import pandas as pd
        if isinstance(path_or_file, str):
            df = pd.read_csv(path_or_file, dtype=str, keep_default_na=False)
        else:
            path_or_file.seek(0)
            df = pd.read_csv(path_or_file, dtype=str, keep_default_na=False)

        cols = {c.lower(): c for c in df.columns}

        def pick(colnames):
            for name in colnames:
                for c in cols:
                    if name in c:
                        return cols[c]
            return None

        date_col = pick(['date', 'transaction date', 'posting date'])
        amount_col = pick(['amount', 'debit', 'credit', 'amt'])
        desc_col = pick(['description', 'narration', 'details', 'desc'])

        for _, row in df.iterrows():
            raw_date = row[date_col] if date_col else None
            raw_amount = row[amount_col] if amount_col else None
            raw_desc = row[desc_col] if desc_col else None
            try:
                d = try_parse_date(raw_date) if raw_date else datetime.now().date()
            except Exception:
                d = datetime.now().date()
            amt = float(str(raw_amount).replace(',', '')) if raw_amount else 0.0
            desc = str(raw_desc) if raw_desc else "Unlabeled Transaction"
            transactions.append({
                'date': d,
                'amount': amt,
                'description': desc,
                'category': None
            })

        print(f"✅ Parsed {len(transactions)} rows with pandas.")
    except Exception as e:
        print("⚠️ Pandas failed:", e)
        pass

    # Fallback: manual CSV parsing
    if not transactions:
        if isinstance(path_or_file, str):
            f = open(path_or_file, 'r', errors='replace', encoding='utf-8')
            close_after = True
        else:
            f = path_or_file
            f.seek(0)
            close_after = False

        try:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                line = ",".join(row)
                try:
                    norm = normalize_row_text(line)
                    transactions.append(norm)
                except Exception:
                    continue
        finally:
            if close_after:
                f.close()

        print(f"✅ Parsed {len(transactions)} rows manually.")

    # ==========================
    # SAVE TO DATABASE
    # ==========================
    for t in transactions:
        try:
            txn = Transaction(
                date=t.get('date') or datetime.now().date(),
                amount=t.get('amount') or 0.0,
                description=t.get('description') or "",
                category=t.get('category') or "Uncategorized"
            )
            db.session.add(txn)
        except Exception as e:
            print("⚠️ Skipped bad row:", e)
            continue

    db.session.commit()
    print(f"💾 Saved {len(transactions)} transactions to the database.")
    return transactions
