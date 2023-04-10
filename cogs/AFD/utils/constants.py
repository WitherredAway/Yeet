import os


EMAIL = os.getenv("myEMAIL")
EXPORT_SUFFIX = "export?format=csv"

UPDATE_CHANNEL_ID = os.getenv("AFD_UPDATE_CHANNEL_ID")
ROW_INDEX_OFFSET = 8  # The number of rows after which the pokemon indexes begin
DEL_ATTRS_TO_UPDATE = ["unc_amount", "unr_amount", "ml_amount"]

APPROVED_TXT = "Approved"

CR = "\r"
TOP_N = 5

HEADERS_FMT = "|   %s   |   %s   |   %s   |   %s   |   %s   |"