import logging
import os
from datetime import date
from typing import Tuple

import pandas as pd
from dotenv import load_dotenv

from send_email import send_email


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_SHEET_ID = "1J5rlEgxpxv8H9u5yK7FpOXLaTUXCgkbr95fcBkT7kOY"
DEFAULT_SHEET_NAME = "invoice_data"
REQUIRED_COLUMNS = {
    "invoice_no",
    "name",
    "email",
    "amount",
    "due_date",
    "reminder_date",
    "has_paid",
}


def build_sheet_url(sheet_id: str, sheet_name: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={sheet_name}"
    )


def load_invoice_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)

    missing_columns = REQUIRED_COLUMNS.difference(df.columns)
    if missing_columns:
        missing_as_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns in source data: {missing_as_text}")

    for column in ("due_date", "reminder_date"):
        df[column] = pd.to_datetime(df[column], errors="coerce")

    return df


def normalize_paid_status(value: object) -> bool:
    if pd.isna(value):
        return False

    normalized = str(value).strip().lower()
    return normalized in {"yes", "true", "1", "paid", "y"}


def validate_row(row: pd.Series) -> Tuple[bool, str]:
    required_text_fields = ("invoice_no", "name", "email", "amount")
    for field in required_text_fields:
        value = row.get(field)
        if pd.isna(value) or not str(value).strip():
            return False, f"missing {field}"

    if pd.isna(row.get("due_date")):
        return False, "invalid due_date"

    if pd.isna(row.get("reminder_date")):
        return False, "invalid reminder_date"

    return True, ""


def send_due_reminders(df: pd.DataFrame) -> dict[str, int]:
    today = date.today()
    sent_count = 0
    skipped_count = 0
    error_count = 0

    for index, row in df.iterrows():
        is_valid, reason = validate_row(row)
        if not is_valid:
            skipped_count += 1
            logger.warning("Skipping row %s: %s", index, reason)
            continue

        if normalize_paid_status(row["has_paid"]):
            logger.info("Skipping row %s: invoice already marked as paid", index)
            skipped_count += 1
            continue

        reminder_date = row["reminder_date"].date()
        if today < reminder_date:
            logger.info("Skipping row %s: reminder date has not arrived yet", index)
            skipped_count += 1
            continue

        try:
            send_email(
                subject=f"[REMINDER] Invoice {row['invoice_no']}",
                recipient_email=str(row["email"]).strip(),
                name=str(row["name"]).strip(),
                due_date=row["due_date"].strftime("%d %b %Y"),
                invoice_no=str(row["invoice_no"]).strip(),
                amount=row["amount"],
            )
            sent_count += 1
        except Exception as exc:
            error_count += 1
            logger.exception("Failed to send email for row %s: %s", index, exc)

    return {"sent": sent_count, "skipped": skipped_count, "errors": error_count}


def main() -> None:
    sheet_id = os.getenv("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID)
    sheet_name = os.getenv("GOOGLE_SHEET_NAME", DEFAULT_SHEET_NAME)
    csv_url = os.getenv("GOOGLE_SHEET_CSV_URL") or build_sheet_url(sheet_id, sheet_name)

    logger.info("Loading invoice data from Google Sheets")
    df = load_invoice_data(csv_url)
    result = send_due_reminders(df)
    logger.info(
        "Reminder run complete | sent=%s skipped=%s errors=%s",
        result["sent"],
        result["skipped"],
        result["errors"],
    )


if __name__ == "__main__":
    main()
