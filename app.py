from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import bcrypt
import os
from dotenv import load_dotenv


app = Flask(__name__)
CORS(app)

load_dotenv()

try:
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017/eventplanner")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)

    db = client["eventplanner"]
    users_collection = db["users"]
    events_collection = db["events"]

    client.admin.command("ping")
    print("✅ MongoDB connected successfully!")
except Exception as e:
    print("❌ MongoDB connection failed:", e)



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



@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"message": "User not found"}), 404

    
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"]):
        return jsonify({"message": "Incorrect password"}), 401

    return jsonify({"message": "Login successful!"}), 200

from bson import ObjectId
def serialize_event(event):
    event["_id"] = str(event["_id"])
    return event

@app.route('/events', methods=['POST'])
def create_event():
    data = request.get_json()

    title = data.get("title")
    date = data.get("date")
    time_ = data.get("time")
    location = data.get("location")
    description = data.get("description")
    organizer_email = data.get("organizer_email")

   
    if not title or not date or not time_ or not organizer_email:
        return jsonify({"message": "Missing required fields"}), 400

    event_doc = {
        "title": title,
        "date": date,
        "time": time_,
        "location": location,
        "description": description,
        "organizer_email": organizer_email,
        "attendees": [],
        "responses": []
    }

    result = events_collection.insert_one(event_doc)

    return jsonify({
        "message": "Event created successfully",
        "event_id": str(result.inserted_id)
    }), 201

@app.route('/events/organized/<email>', methods=['GET'])
def get_organized_events(email):
    events_cursor = events_collection.find({"organizer_email": email})
    events = [serialize_event(e) for e in events_cursor]

    return jsonify(events), 200

@app.route('/events/invited/<email>', methods=['GET'])
def get_invited_events(email):
    events_cursor = events_collection.find({"attendees": {"$in": [email]}})
    events = [serialize_event(e) for e in events_cursor]
    return jsonify(events), 200

@app.route('/events/all', methods=['GET'])
def get_all_events():
    events_cursor = events_collection.find({})
    events = [serialize_event(e) for e in events_cursor]
    return jsonify(events), 200


@app.route('/events/invite', methods=['POST'])
def invite_user():
    data = request.get_json()
    event_id = data.get("event_id")
    email = data.get("email")

    if not event_id or not email:
        return jsonify({"message": "event_id and email are required"}), 400

    try:
        event_obj_id = ObjectId(event_id)
    except:
        return jsonify({"message": "Invalid event_id format"}), 400

    event = events_collection.find_one({"_id": event_obj_id})
    if not event:
        return jsonify({"message": "Event not found"}), 404

    
    if "attendees" in event and email in event["attendees"]:
        return jsonify({"message": "User already invited"}), 200

   
    events_collection.update_one(
        {"_id": event_obj_id},
        {"$addToSet": {"attendees": email}}
    )

    return jsonify({"message": "User invited successfully"}), 200

@app.route('/events/respond', methods=['POST'])
def respond_to_event():
    data = request.get_json()
    event_id = data.get("event_id")
    email = data.get("email")
    status = data.get("status")

    if not event_id or not email or not status:
        return jsonify({"message": "event_id, email and status are required"}), 400

    if status not in ["Going", "Maybe", "Not Going"]:
        return jsonify({"message": "Invalid status value"}), 400

    try:
        event_obj_id = ObjectId(event_id)
    except:
        return jsonify({"message": "Invalid event_id format"}), 400

    event = events_collection.find_one({"_id": event_obj_id})
    if not event:
        return jsonify({"message": "Event not found"}), 404

   
    events_collection.update_one(
        {"_id": event_obj_id},
        {"$pull": {"responses": {"email": email}}}
    )

    
    events_collection.update_one(
        {"_id": event_obj_id},
        {"$push": {"responses": {"email": email, "status": status}}}
    )

    return jsonify({"message": "Response saved successfully"}), 200


@app.route('/events/responses/<event_id>', methods=['GET'])
def get_event_responses(event_id):
    try:
        event_obj_id = ObjectId(event_id)
    except:
        return jsonify({"message": "Invalid event_id format"}), 400

    event = events_collection.find_one({"_id": event_obj_id})
    if not event:
        return jsonify({"message": "Event not found"}), 404

    responses = event.get("responses", [])

    return jsonify({
        "event_id": str(event["_id"]),
        "title": event.get("title"),
        "responses": responses
    }), 200


@app.route('/events/search', methods=['GET'])
def search_events():
    keyword = request.args.get('keyword', '').strip()
    date = request.args.get('date', '').strip()
    role = request.args.get('role', '').strip()  # '' / organizer / attendee
    user_email = request.args.get('user_email', '').strip()

    query = {}

   
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
        ]

    
    if date:
        query["date"] = date

   
    events = list(events_collection.find(query))

    
    if role and role != "any" and user_email:
        filtered = []
        for ev in events:
            organizer_email = ev.get("organizer_email")
            attendees = ev.get("attendees", [])
            responses = ev.get("responses", [])

            if role == "organizer":
                
                if organizer_email == user_email:
                    ev["user_role"] = "Organizer"
                    filtered.append(ev)

            elif role == "attendee":
               
                is_attendee = user_email in attendees or any(
                    r.get("email") == user_email for r in responses
                )
                if is_attendee:
                    ev["user_role"] = "Attendee"
                    filtered.append(ev)

        events = filtered
    else:
       
        if user_email:
            for ev in events:
                if ev.get("organizer_email") == user_email:
                    ev["user_role"] = "Organizer"
                elif user_email in ev.get("attendees", []):
                    ev["user_role"] = "Attendee"

    
    for ev in events:
        ev["_id"] = str(ev["_id"])

    return jsonify(events), 200


@app.route('/events/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    email = request.args.get("email")  

    if not email:
        return jsonify({"message": "Organizer email is required"}), 400

    try:
        event_obj_id = ObjectId(event_id)
    except:
        return jsonify({"message": "Invalid event_id format"}), 400

    
    event = events_collection.find_one({"_id": event_obj_id})
    if not event:
        return jsonify({"message": "Event not found"}), 404

    # Check if the requester is the organizer
    if event["organizer_email"] != email:
        return jsonify({"message": "You are not the organizer of this event"}), 403

    # Delete event
    events_collection.delete_one({"_id": event_obj_id})

    return jsonify({"message": "Event deleted successfully"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



