from flask import Flask, request, jsonify
import logging
from datetime import datetime
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/identify_callback', methods=['POST'])
def identify_callback():
    """
    Handle identify callback from face recognition device
    """
    try:
        # Log the received data
        data = request.form.to_dict()
        
        # Parse JSON data if present
        alcohol_data = {}
        if 'data' in data and data['data']:
            try:
                alcohol_data = json.loads(data['data'])
            except json.JSONDecodeError:
                alcohol_data = {"raw": data['data']}
        
        # Extract and log important information
        logger.info("=" * 60)
        logger.info("IDENTIFY CALLBACK RECEIVED")
        logger.info("=" * 60)
        logger.info(f"Device: {data.get('deviceKey', 'Unknown')}")
        logger.info(f"Person ID: {data.get('personId', 'Unknown')}")
        logger.info(f"Person Name: {data.get('personName', 'Unknown')}")
        logger.info(f"Recognition Type: {data.get('type', 'Unknown')}")
        logger.info(f"Timestamp: {data.get('time', 'Unknown')}")
        logger.info(f"Search Score: {data.get('searchScore', 'N/A')}")
        logger.info(f"Liveness Score: {data.get('livenessScore', 'N/A')}")
        logger.info(f"Mask Status: {data.get('mask', 'N/A')}")
        logger.info(f"Device IP: {data.get('ip', 'N/A')}")
        
        # Log alcohol detection data if available
        if alcohol_data:
            logger.info("Alcohol Detection Data:")
            for key, value in alcohol_data.items():
                logger.info(f"  {key}: {value}")
        
        # Log image info (but not the full base64 to avoid log spam)
        if 'imgBase64' in data:
            img_size = len(data['imgBase64'])
            logger.info(f"Image Size: {img_size} bytes (base64)")
        
        if 'path' in data:
            logger.info(f"Image URL: {data['path']}")
        
        logger.info("=" * 60)
        
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
    """
    try:
        # Log the received data
        data = request.form.to_dict()
        
        logger.info("=" * 60)
        logger.info("HEARTBEAT RECEIVED")
        logger.info("=" * 60)
        logger.info(f"Device: {data.get('deviceKey', 'Unknown')}")
        logger.info(f"Timestamp: {data.get('time', 'Unknown')}")
        logger.info(f"Registered Persons: {data.get('personCount', 'N/A')}")
        logger.info(f"Registered Faces: {data.get('faceCount', 'N/A')}")
        logger.info(f"Device Version: {data.get('version', 'N/A')}")
        logger.info(f"Device IP: {data.get('ip', 'N/A')}")
        logger.info("=" * 60)
        
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
        "service": "Face Device Callback Server",
        "endpoints": {
            "identify_callback": "POST /identify_callback",
            "heartbeat_callback": "POST /heartbeat_callback",
            "health": "GET /health"
        }
    })

@app.route('/test', methods=['GET', 'POST'])
def test_endpoint():
    """Test endpoint to simulate device callbacks"""
    return jsonify({
        "message": "Test endpoint working",
        "usage": {
            "identify_callback": "POST form data to /identify_callback",
            "heartbeat_callback": "POST form data to /heartbeat_callback"
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
