import os
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder="app/templates")

@app.route("/")
def home():
    return "Welcome to Smart Stock Bot!"

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    # … your real prediction logic here …
    return jsonify({"prediction": "buy"})

@app.route("/ui")
def ui():
    return render_template("index.html")

@app.route("/models", methods=["GET"])
def list_models():
    files = sorted(os.listdir("models"))
    models = [f for f in files if f.endswith(".h5")]
    return jsonify(models)

if __name__ == "__main__":
    # Changed to port 5001 to avoid macOS AirPlay conflicts
    app.run(debug=True, host="0.0.0.0", port=5001)
