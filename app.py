from flask import Flask, request, jsonify
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/identify_callback', methods=['POST'])
def identify_callback():
    """
    Handle identify callback from face recognition device
    Expected parameters based on the documentation:
    - deviceKey: Device serial number
    - personId: Person ID
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
        
        # Log additional details
        logger.info(f"Callback from device: {data.get('deviceKey', 'Unknown')}")
        logger.info(f"Person ID: {data.get('personId', 'Unknown')}")
        logger.info(f"Recognition type: {data.get('type', 'Unknown')}")
        logger.info(f"Temperature: {data.get('temperature', 'N/A')}")
        
        # Return the expected response format
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
        
        # Log device status
        logger.info(f"Heartbeat from device: {data.get('deviceKey', 'Unknown')}")
        logger.info(f"Registered persons: {data.get('personCount', 'N/A')}")
        logger.info(f"Registered faces: {data.get('faceCount', 'N/A')}")
        logger.info(f"Device version: {data.get('version', 'N/A')}")
        
        # No response data needed according to documentation
        return '', 200
    
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        return '', 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Face Device Callback Server"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
