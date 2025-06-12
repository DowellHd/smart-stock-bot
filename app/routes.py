import os
import numpy as np
from flask import Flask, request, jsonify, render_template
from tensorflow.keras.models import load_model

app = Flask(__name__)

# simple in-memory cache so we only load each .h5 once
_MODEL_CACHE: dict[str, any] = {}

def get_model(filename: str):
    """Load a model from models/<filename>, caching on first use."""
    if filename not in _MODEL_CACHE:
        path = os.path.join("models", filename)
        _MODEL_CACHE[filename] = load_model(path)
    return _MODEL_CACHE[filename]

@app.route("/")
def home():
    return "Welcome to Smart Stock Bot!"

@app.route("/ui")
def ui():
    return render_template("index.html")

@app.route("/models", methods=["GET"])
def list_models():
    files = sorted(os.listdir("models"))
    models = [f for f in files if f.endswith(".h5")]
    return jsonify(models)

@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(force=True)
    # expected payload keys: "state": list[float], optional "model": filename
    ticker = payload.get("ticker", "AAPL")
    model_file = payload.get("model", f"dqn_{ticker}_final.h5")
    model = get_model(model_file)

    # build a batch of size 1 for Keras
    state = np.array(payload["state"])[np.newaxis, :]
    q_vals = model.predict(state, verbose=0)[0]
    action = int(np.argmax(q_vals))

    return jsonify({"action": action})

if __name__ == "__main__":
    # run on 5001 to avoid macOS AirPlay conflicts
    app.run(debug=True, host="0.0.0.0", port=5001)