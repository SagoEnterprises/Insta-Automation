
from fastapi import FastAPI, Request
import os
import re
import json
import requests
import gspread

from datetime import datetime
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")

# -----------------------------
# GOOGLE SHEETS
# -----------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

service_account_info = json.loads(
    os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
)

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES,
)

gc = gspread.authorize(creds)

spreadsheet = gc.open(SHEET_NAME)

keyword_sheet = spreadsheet.worksheet("KeywordRules")
settings_sheet = spreadsheet.worksheet("Settings")
audit_sheet = spreadsheet.worksheet("AuditLog")
processed_sheet = spreadsheet.worksheet("processed_comments")

# -----------------------------
# HELPERS
# -----------------------------


def get_setting(key):

    rows = settings_sheet.get_all_records()

    for row in rows:
        if row["key"] == key:
            return row["value"]

    return ""


def is_processed(comment_id):

    rows = processed_sheet.get_all_records()

    for row in rows:
        if str(row["comment_id"]) == str(comment_id):
            return True

    return False


def mark_processed(
    comment_id,
    media_id,
    username,
    comment_text,
):

    processed_sheet.append_row([
        comment_id,
        media_id,
        username,
        comment_text,
        datetime.utcnow().isoformat(),
    ])


def write_audit(
    username,
    media_id,
    comment,
    action,
):

    audit_sheet.append_row([
        datetime.utcnow().isoformat(),
        username,
        media_id,
        comment,
        action,
    ])


def keyword_matches(comment_text):

    rows = keyword_sheet.get_all_records()

    for row in rows:

        active = str(
            row.get("active", "")
        ).upper()

        if active != "TRUE":
            continue

        pattern = row.get(
            "regex_pattern",
            ""
        )

        if not pattern:
            continue

        try:

            if re.search(
                pattern,
                comment_text,
            ):
                return True

        except Exception as ex:

            print(
                f"Regex Error: {pattern}"
            )

            print(str(ex))

    return False


def reply_to_comment(
    comment_id,
    reply_text,
):

    url = (
        f"https://graph.facebook.com/v25.0/"
        f"{comment_id}/replies"
    )

    response = requests.post(
        url,
        data={
            "message": reply_text,
            "access_token": ACCESS_TOKEN,
        },
        timeout=30,
    )

    print("Reply API Response:")
    print(response.text)

    return response.ok


# -----------------------------
# HEALTH CHECK
# -----------------------------

@app.get("/")
async def root():

    return {
        "status": "running"
    }


@app.get("/test-sheet")
async def test_sheet():

    return keyword_sheet.get_all_records()


# -----------------------------
# WEBHOOK VERIFICATION
# -----------------------------

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None,
):

    if (
        hub_mode == "subscribe"
        and hub_verify_token == VERIFY_TOKEN
    ):
        return int(hub_challenge)

    return {
        "error": "verification failed"
    }


# -----------------------------
# WEBHOOK EVENTS
# -----------------------------

@app.post("/webhook")
async def webhook(request: Request):

    payload = await request.json()

    print("========== WEBHOOK ==========")
    print(payload)

    try:

        for entry in payload.get(
            "entry",
            []
        ):

            for change in entry.get(
                "changes",
                []
            ):

                if (
                    change.get("field")
                    != "comments"
                ):
                    continue

                value = change.get(
                    "value",
                    {}
                )

                comment_id = value.get(
                    "id"
                )

                comment_text = value.get(
                    "text",
                    ""
                )

                media_id = (
                    value.get(
                        "media",
                        {}
                    ).get(
                        "id",
                        ""
                    )
                )

                username = (
                    value.get(
                        "from",
                        {}
                    ).get(
                        "username",
                        ""
                    )
                )

                print(
                    f"Comment: {comment_text}"
                )

                if not comment_id:
                    continue

                if is_processed(
                    comment_id
                ):

                    print(
                        "Already processed"
                    )

                    continue

                if not keyword_matches(
                    comment_text
                ):

                    write_audit(
                        username,
                        media_id,
                        comment_text,
                        "KEYWORD_NOT_MATCHED",
                    )

                    continue

                template = get_setting(
                    "comment_reply_template"
                )

                reply_text = (
                    template.replace(
                        "{username}",
                        username,
                    )
                )

                success = (
                    reply_to_comment(
                        comment_id,
                        reply_text,
                    )
                )

                if success:

                    write_audit(
                        username,
                        media_id,
                        comment_text,
                        "COMMENT_REPLIED",
                    )

                    mark_processed(
                        comment_id,
                        media_id,
                        username,
                        comment_text,
                    )

                else:

                    write_audit(
                        username,
                        media_id,
                        comment_text,
                        "COMMENT_REPLY_FAILED",
                    )

    except Exception as ex:

        print("ERROR")
        print(str(ex))

    return {
        "status": "ok"
    }
