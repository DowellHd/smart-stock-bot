import numpy as np
import pandas as pd
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return "Welcome to Smart Stock Bot!"

@app.route("/predict", methods=["POST"])
def predict():
    """
    Expects JSON payload: { … }
    Returns JSON: e.g. {"prediction":"buy"} or {"action":0|1|2}
    """
    data = request.get_json(force=True)
    # TODO: replace with real prediction logic
    return jsonify({"prediction": "buy"})

# Add more routes as needed

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
