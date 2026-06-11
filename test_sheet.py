import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=SCOPES,
)

gc = gspread.authorize(creds)

sheet = gc.open("Instagram Automation")

worksheet = sheet.worksheet("KeywordRules")

print(worksheet.get_all_records())
