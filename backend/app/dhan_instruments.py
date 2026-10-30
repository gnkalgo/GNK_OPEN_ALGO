"""Operator-only refresh of explicitly selected NSE EQ instruments from Dhan."""

import argparse
import csv
from decimal import Decimal

import httpx
from sqlalchemy import select

from .db import SessionLocal
from .models import DhanInstrument, now

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"


def parse_rows(lines, selected):
    found = {}
    for row in csv.DictReader(lines):
        security_id = row.get("SECURITY_ID", "")
        if security_id not in selected or row.get("EXCH_ID") != "NSE" or row.get("SEGMENT") != "E":
            continue
        if row.get("SERIES") != "EQ" or row.get("INSTRUMENT") != "EQUITY":
            continue
        if security_id in found:
            raise ValueError("Ambiguous security ID in Dhan master")
        lot = Decimal(row["LOT_SIZE"])
        tick = Decimal(row["TICK_SIZE"]) / 100  # Dhan documents this field in paise.
        lower, upper = Decimal(row["SM_LOWER_LIMIT"]), Decimal(row["SM_UPPER_LIMIT"])
        freeze = Decimal(row["SM_FREEZE_QTY"])
        if not all(v.is_finite() and v > 0 for v in (lot, tick, lower, upper, freeze)):
            raise ValueError("Invalid instrument risk metadata")
        if lot != 1 or freeze != int(freeze) or lower >= upper or not row.get("SYMBOL_NAME"):
            raise ValueError("Unsupported instrument metadata")
        found[security_id] = dict(
            security_id=security_id,
            name=row["SYMBOL_NAME"][:120],
            lot_size=int(lot),
            tick_size=tick,
            lower_limit=lower,
            upper_limit=upper,
            freeze_quantity=int(freeze),
            enabled=row.get("ASM_GSM_FLAG") == "N" and row.get("BUY_SELL_INDICATOR") == "A",
            synced_at=now(),
        )
    if set(found) != selected:
        raise ValueError("Selected IDs are missing or not supported NSE EQ equities")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security-ids", required=True)
    args = parser.parse_args()
    selected = set(args.security_ids.split(","))
    if not selected or len(selected) > 50 or any(not value.isdigit() for value in selected):
        raise SystemExit("Supply 1-50 comma-separated numeric security IDs")
    with httpx.stream("GET", MASTER_URL, timeout=30, follow_redirects=False) as response:
        response.raise_for_status()
        rows = parse_rows(response.iter_lines(), selected)
    with SessionLocal() as db:
        # An unsuccessful import never updates timestamps or leaves a partial catalog.
        for item in db.scalars(select(DhanInstrument)).all():
            item.enabled = False
        for security_id, values in rows.items():
            item = db.get(DhanInstrument, security_id)
            if item is None:
                item = DhanInstrument(security_id=security_id)
                db.add(item)
            for key, value in values.items():
                setattr(item, key, value)
        db.commit()
    print("Dhan NSE EQ catalog refreshed. No orders were sent.")


if __name__ == "__main__":
    main()
