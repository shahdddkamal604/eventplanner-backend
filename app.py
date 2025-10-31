from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import bcrypt
import os
from dotenv import load_dotenv
import certifi

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()

try:
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
    db = client["sample_mflix"]
    users_collection = db["users"]
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ MongoDB connection failed:", e)


# ========== SIGNUP ==========
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if users_collection.find_one({"email": email}):
        return jsonify({"message": "User already exists"}), 400

    hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    users_collection.insert_one({"email": email, "password": hashed_pw})
    return jsonify({"message": "Signup successful!"}), 201


# ========== LOGIN ==========
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Compare hashed password
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return jsonify({"message": "Incorrect password"}), 401

    return jsonify({"message": "Login successful!"}), 200


if __name__ == "__main__":
    app.run(debug=True)


