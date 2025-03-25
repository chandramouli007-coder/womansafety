from flask import Flask, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, JWTManager
from flask_cors import CORS
from pymongo import MongoClient
import bcrypt
import hashlib
from twilio.rest import Client
import os

from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests
app.config['JWT_SECRET_KEY'] = 'woman_safety_app'
jwt = JWTManager(app)

# MongoDB Connection
client = MongoClient("mongodb+srv://mouliinindia05:mouli05052002@cluster0.o6dco.mongodb.net/")
db = client["woman"]
users_collection = db["users"]



TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)



@app.route('/')
def home():
    return jsonify({"message": "Hello World!"}) 

@app.route('/api/profile/<user_id>', methods=['GET'])
def get_profile(user_id):
    try:
        print("User ID:", user_id)
        print("INSIDE GET PROFILE")
        user = users_collection.find_one({'user_id': user_id})
        if user:
            # Convert MongoDB document to JSON-friendly format
            user_data = {
                'name': user.get('name', 'N/A'),
                'phone': user.get('phone', 'N/A'),
                'emergency_contacts': user.get('emergency_contacts', [])
            }
            return jsonify(user_data), 200
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        user_id = data['user_id']
        name = data['name']
        phone = data['phone']
        emergency_contacts = data['emergency_contacts']

        # Hash password using bcrypt
        password = data['password']

        # Check if user already exists (e.g., by phone)
        if users_collection.find_one({'phone': phone}):
            return jsonify({'error': 'User with this phone already exists'}), 400

        user_data = {
            'user_id': user_id,
            'name': name,
            'phone': phone,
            'emergency_contacts': emergency_contacts,
            'password': password  # Store the hashed password (bytes)
        }
        users_collection.insert_one(user_data)
        return jsonify({'message': 'User created', 'user_id': user_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        name = data.get('name')
        password = data.get('password')

        user = users_collection.find_one({"name": name})
        print(user, name, password)
        
        if user:
            stored_hashed_password = user['password']

            if stored_hashed_password == password:
                return jsonify({'message': 'Login successful', 'user_id': user['user_id']}), 200

        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/send_alert', methods=['POST'])
def send_alert():
    try:
        data = request.get_json()
        print("Alert data:", data)
        user_id = data['user_id']
        cctv_name = data['cctv_name']

        user = users_collection.find_one({'user_id': user_id})
        if not user:
            return jsonify({'error': 'User not found'}), 404

        emergency_contacts = user.get('emergency_contacts', [])
        if not emergency_contacts:
            return jsonify({'error': 'No emergency contacts found'}), 400

        for contact in emergency_contacts:
            if contact['number']:
                message = f"Emergency Alert: {user['name']} in {cctv_name}!"
                try:
                    twilio_client.messages.create(
                        body=message,
                        from_=TWILIO_PHONE_NUMBER,
                        to=f"+{contact['number']}"  # Assuming 10-digit numbers; add country code if needed (e.g., +1 for US)
                    )
                    print(f"SMS sent to {contact['number']}")
                except TwilioRestException as e:
                    print(f"Twilio error: {str(e)}")
                    return jsonify({'error': f"Failed to send SMS: {str(e)}"}), 500

        return jsonify({'message': 'Emergency alerts sent'}), 200
    except Exception as e:
        print("Alert error:", str(e))
        return jsonify({'error': str(e)}), 500



@app.route('/api/update_contact', methods=['PATCH'])
def update_contact():
    try:
        data = request.get_json()
        print("Update contact data:", data)
        user_id = data['user_id']
        contact_index = data['contact_index']
        emergency_contact = data['emergency_contact']

        # Find the user
        user = users_collection.find_one({'user_id': user_id})
        if not user:
            print("User not found for user_id:", user_id)
            return jsonify({'error': 'User not found'}), 404

        # Check if index is valid
        if contact_index < 0 or contact_index >= len(user['emergency_contacts']):
            print("Invalid contact index:", contact_index)
            return jsonify({'error': 'Invalid contact index'}), 400

        # Update the specific contact
        result = users_collection.update_one(
            {'user_id': user_id},
            {'$set': {f'emergency_contacts.{contact_index}': emergency_contact}}
        )
        print("Matched count:", result.matched_count)

        if result.matched_count > 0:
            print("Updated contact at index", contact_index, "for user_id:", user_id)
            return jsonify({'message': 'Contact updated'}), 200
        else:
            return jsonify({'error': 'Update failed'}), 500
    except Exception as e:
        print("Update contact error:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
 
