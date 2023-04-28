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

COL_OFFSET = 1  # How many rows after the pokemon rows start.
CLAIM_LIMIT = 5
AFD_ROLE_ID = 1095381341178183851
AFD_ADMIN_ROLE_ID = 1095393318281678848
LOG_CHANNEL_ID = 1098442880202313779
