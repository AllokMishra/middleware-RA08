from flask import Flask, request, jsonify
import logging
from datetime import datetime
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('biometric_integration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Frappe HR Configuration
FRAPPE_URL = os.getenv('FRAPPE_URL', 'https://your-frappe-instance.com')
API_KEY = os.getenv('FRAPPE_API_KEY')
API_SECRET = os.getenv('FRAPPE_API_SECRET')
CHECKIN_SERIAL = os.getenv('CHECKIN_DEVICE_SERIAL', 'CHECKIN_DEVICE_SERIAL_NUMBER')
CHECKOUT_SERIAL = os.getenv('CHECKOUT_DEVICE_SERIAL', 'CHECKOUT_DEVICE_SERIAL_NUMBER')

def create_frappe_checkin(data, machine_type):
    """
    Create Employee Checkin in Frappe HR via API
    """
    try:
        # Map machine location to device_id
        device_mapping = {
            "checkin": "Check-In-Machine-01",
            "checkout": "Check-Out-Machine-01"
        }
        
        # Get person ID (employee device ID)
        person_id = data.get('personId')
        if not person_id or person_id == 'Unknown':
            logger.warning(f"No valid personId found in data: {data}")
            return False
        
        # Convert timestamp format
        timestamp = data.get('time')
        if timestamp:
            try:
                # Handle different timestamp formats
                if len(timestamp) == 10:  # Unix timestamp (seconds)
                    dt = datetime.fromtimestamp(int(timestamp))
                elif len(timestamp) == 13:  # Unix timestamp (milliseconds)
                    dt = datetime.fromtimestamp(int(timestamp) / 1000)
                else:
                    # Try to parse as string
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                
                formatted_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S.000000')
            except Exception as time_error:
                logger.warning(f"Timestamp conversion error: {time_error}, using current time")
                formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.000000')
        else:
            formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.000000')
        
        # Determine log type based on machine type
        log_type = "IN" if machine_type == "checkin" else "OUT"
        
        # API endpoint
        url = f"{FRAPPE_URL}/api/method/hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
        
        # Request payload
        payload = {
            "employee_field_value": person_id,
            "timestamp": formatted_timestamp,
            "device_id": device_mapping.get(machine_type, "Biometric-Device"),
            "log_type": log_type,
            "employee_fieldname": "attendance_device_id",
            "skip_auto_attendance": 0  # Let Frappe handle attendance automatically
        }
        
        # Add optional fields if available
        if data.get('temperature'):
            payload["custom_temperature"] = data.get('temperature')
        if data.get('mask'):
            payload["custom_mask_status"] = data.get('mask')
        
        # Headers with authentication
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"token {API_KEY}:{API_SECRET}"
        }
        
        logger.info(f"Sending to Frappe HR: {payload}")
        
        # Make API request with timeout
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('message'):
                logger.info(f"Successfully created checkin in Frappe: {result['message']}")
            else:
                logger.info(f"Successfully created checkin in Frappe: {result}")
            return True
        else:
            logger.error(f"Frappe API error: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("Frappe API request timed out")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Frappe instance")
        return False
    except Exception as e:
        logger.error(f"Error creating Frappe checkin: {str(e)}")
        return False

@app.route('/identify_callback', methods=['POST'])
def identify_callback():
    """
    Handle identify callback from face recognition device
    Expected parameters based on the documentation:
    - deviceKey: Device serial number
    - personId: Person ID (should match attendance_device_id in Frappe)
    - time: Identify record timestamp
    - type: Recognition type (face_0, face_1, face_2, etc.)
    - path: Photo access URL
    - imgBase64: Snap photo base64 string
    - data: Additional data (ID card info, etc.)
    - ip: Device LAN IP address
    - searchScore: Recognition score
    - livenessScore: Liveness score
    - temperature: Personnel temperature
    - standard: Temperature abnormal value
    - temperatureState: Body temperature status
    - mask: Mask status (-1, 0, 1)
    """
    try:
        # Log the received data
        data = request.form.to_dict()
        logger.info(f"Identify callback received: {data}")
        
        device_key = data.get('deviceKey', 'Unknown')
        
        # Determine machine type based on device serial
        if device_key == CHECKIN_SERIAL:
            machine_type = "checkin"
        elif device_key == CHECKOUT_SERIAL:
            machine_type = "checkout"
        else:
            machine_type = "unknown"
            logger.warning(f"Unknown device serial: {device_key}")
        
        logger.info(f"Callback from {machine_type} device: {device_key}")
        logger.info(f"Person ID: {data.get('personId', 'Unknown')}")
        logger.info(f"Timestamp: {data.get('time', 'N/A')}")
        logger.info(f"Temperature: {data.get('temperature', 'N/A')}")
        logger.info(f"Recognition score: {data.get('searchScore', 'N/A')}")
        
        # Send to Frappe HR only for known devices
        if machine_type in ["checkin", "checkout"]:
            success = create_frappe_checkin(data, machine_type)
            if success:
                logger.info("Successfully sent to Frappe HR")
            else:
                logger.warning("Failed to send to Frappe HR - check logs for details")
        else:
            logger.warning("Skipping Frappe integration for unknown device")
        
        # Return the expected response format for biometric device
        response = {"result": 1, "code": "000"}
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error processing identify callback: {str(e)}")
        return jsonify({"result": 0, "code": "500"}), 500

@app.route('/heartbeat_callback', methods=['POST'])
def heartbeat_callback():
    """
    Handle heartbeat callback from face recognition device
    Expected parameters:
    - deviceKey: Device serial number
    - time: Timestamp
    - personCount: Number of registered personnel
    - faceCount: Number of registered photos
    - ip: Device IP address
    - version: Device current version number
    """
    try:
        # Log the received data
        data = request.form.to_dict()
        logger.info(f"Heartbeat received: {data}")
        
        device_key = data.get('deviceKey', 'Unknown')
        
        # Determine machine type
        if device_key == CHECKIN_SERIAL:
            machine_type = "checkin"
        elif device_key == CHECKOUT_SERIAL:
            machine_type = "checkout"
        else:
            machine_type = "unknown"
        
        logger.info(f"Heartbeat from {machine_type} device: {device_key}")
        logger.info(f"Registered persons: {data.get('personCount', 'N/A')}")
        logger.info(f"Registered faces: {data.get('faceCount', 'N/A')}")
        logger.info(f"Device version: {data.get('version', 'N/A')}")
        logger.info(f"Device IP: {data.get('ip', 'N/A')}")
        
        # No response data needed according to documentation
        return '', 200
    
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        return '', 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    frappe_status = "connected" if test_frappe_connection() else "disconnected"
    
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Face Device Callback Server",
        "frappe_connection": frappe_status,
        "checkin_device_configured": bool(CHECKIN_SERIAL and CHECKIN_SERIAL != 'CHECKIN_DEVICE_SERIAL_NUMBER'),
        "checkout_device_configured": bool(CHECKOUT_SERIAL and CHECKOUT_SERIAL != 'CHECKOUT_DEVICE_SERIAL_NUMBER')
    })

def test_frappe_connection():
    """Test connection to Frappe instance"""
    try:
        if not all([FRAPPE_URL, API_KEY, API_SECRET]):
            return False
            
        url = f"{FRAPPE_URL}/api/method/version"
        headers = {"Authorization": f"token {API_KEY}:{API_SECRET}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

@app.route('/test_frappe', methods=['GET'])
def test_frappe_integration():
    """Test endpoint to verify Frappe integration"""
    test_data = {
        "personId": "test_employee_id",  # Replace with actual test employee ID
        "time": str(int(datetime.now().timestamp())),
        "deviceKey": CHECKIN_SERIAL
    }
    
    success = create_frappe_checkin(test_data, "checkin")
    
    return jsonify({
        "success": success,
        "frappe_connection": test_frappe_connection(),
        "test_data": test_data
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    # Log configuration at startup
    logger.info("Starting Biometric Integration Server")
    logger.info(f"Frappe URL: {FRAPPE_URL}")
    logger.info(f"Check-in Device: {CHECKIN_SERIAL}")
    logger.info(f"Check-out Device: {CHECKOUT_SERIAL}")
    logger.info(f"Frappe Connection: {'Connected' if test_frappe_connection() else 'Disconnected'}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
