from flask import Flask, request, jsonify
import requests
import logging

# Setup
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Device config - UPDATE THESE!
DEVICE_IP = "192.168.1.100"  # Change to your device IP
DEVICE_KEY = "0A09010BC2687C45"  # Change to your device serial
SECRET = "tdx"  # Change to your device password
BASE_URL = f"http://{DEVICE_IP}:8190/api"

@app.route('/identify_callback', methods=['POST'])
def identify_callback():
    """Receive face recognition events"""
    data = request.form.to_dict()
    print(f"📱 Recognition event: {data.get('personId', 'Unknown')} - {data.get('type', 'Unknown')}")
    return jsonify({"result": 1, "code": "000"})

@app.route('/heartbeat_callback', methods=['POST'])
def heartbeat_callback():
    """Receive device heartbeat"""
    data = request.form.to_dict()
    print(f"❤️  Heartbeat: {data.get('deviceKey')} - {data.get('personCount')} people")
    return ''

def test_connection():
    """Test if we can connect to the device"""
    try:
        data = {"deviceKey": DEVICE_KEY, "secret": SECRET}
        response = requests.post(f"{BASE_URL}/device/config", data=data, timeout=5)
        print(f"🔗 Connection test: {response.status_code} - {response.text}")
        return response.json().get('code') == '000'
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def add_test_person():
    """Add a test person to the device"""
    data = {
        "deviceKey": DEVICE_KEY,
        "secret": SECRET,
        "id": "test_user_1",
        "name": "Test User"
    }
    response = requests.post(f"{BASE_URL}/person/add", data=data)
    print(f"👤 Add person: {response.status_code} - {response.text}")
    return response.json().get('code') == '000'

if __name__ == '__main__':
    print("🚀 Starting Face Recognition Test Server...")
    
    # Test connection first
    if test_connection():
        print("✅ Device connected successfully!")
        # Try to add a test person
        if add_test_person():
            print("✅ Test person added!")
        else:
            print("❌ Failed to add test person")
    else:
        print("❌ Cannot connect to device - check IP and credentials")
    
    print("🌐 Server running on http://localhost:5000")
    print("📞 Callbacks: /identify_callback, /heartbeat_callback")
    app.run(host='0.0.0.0', port=5000, debug=True)
