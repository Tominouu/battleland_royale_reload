import os

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))

# Default TitleId the client sends
TITLE_ID = os.environ.get("TITLE_ID", "FC88D")

# Will be used as <TitleId>.playfabapi.com
PLAYFAB_DOMAIN = f"{TITLE_ID}.playfabapi.com"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "storage")
