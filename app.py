from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def hello():
    return "Halo Dunia dari Aplikasi Sederhana!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)