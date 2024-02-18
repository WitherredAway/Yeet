import os


SHEET_URL = os.getenv("AFD_SHEET_URL")
AFD_GIST_URL = os.getenv("AFD_GIST_URL")
AFD_CREDITS_GIST_URL = os.getenv("AFD_CREDITS_GIST_URL")

IMGUR_API = "https://api.imgur.com/3/album/%s/images"
SPREADSHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

SUBMISSION_URL = "https://example.com"  # TODO USE PROPER SUBMISSION URL
