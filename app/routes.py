import os
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder="app/templates")

@app.route("/")
def home():
    return "Welcome to Smart Stock Bot!"

@app.route("/predict", methods=["POST"])
def predict():
    # Example: get data from request and return a dummy prediction
    data = request.get_json(force=True)
    # … your real prediction logic here …
    return jsonify({"prediction": "buy"})

@app.route("/ui")
def ui():
    """Dashboard page listing available model checkpoints."""
    return render_template("index.html")

@app.route("/models", methods=["GET"])
def list_models():
    """
    Return a JSON array of all .h5 files in the models/ directory.
    """
    files = sorted(os.listdir("models"))
    models = [f for f in files if f.endswith(".h5")]
    return jsonify(models)

if __name__ == "__main__":
    # Run the Flask development server on port 5001 to avoid conflicts
    app.run(debug=True, host="0.0.0.0", port=5001)