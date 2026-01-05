import os
import numpy as np
from flask import Flask, request, jsonify, render_template
from tensorflow.keras.models import load_model

app = Flask(__name__, template_folder="app/templates")

# cache loaded models so we only load each file once
_models = {}

@app.route("/")
def home():
    return "Welcome to Smart Stock Bot!"

@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(force=True)
    state = np.array(payload["state"])[np.newaxis, :]  # batch of 1

    model_name = payload.get("model")
    if not model_name:
        return jsonify({"error": "no model specified"}), 400

    # load (and cache) the Keras model
    if model_name not in _models:
        path = os.path.join("models", model_name)
        if not os.path.exists(path):
            return jsonify({"error": f"model '{model_name}' not found"}), 404
        _models[model_name] = load_model(path)
    model = _models[model_name]

    # do the real prediction
    q_vals = model.predict(state, verbose=0)[0]
    action = int(np.argmax(q_vals))

    return jsonify({"action": action})

@app.route("/models", methods=["GET"])
def list_models():
    files = sorted(os.listdir("models"))
    models = [f for f in files if f.endswith(".h5")]
    return jsonify(models)

@app.route("/ui")
def ui():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug = True, host="0.0.0.0", port = 5001)