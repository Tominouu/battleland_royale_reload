import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from flask_cors import CORS
from playfab.router import playfab_bp
from playfab.internal import internal_bp
from config.settings import HOST, PORT

app = Flask(__name__)
CORS(app)

app.register_blueprint(internal_bp)
app.register_blueprint(playfab_bp)

@app.route("/")
def index():
    return {"service": "Battlelands Private Server", "status": "running"}

if __name__ == "__main__":
    print(f"Starting Battlelands private server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)
