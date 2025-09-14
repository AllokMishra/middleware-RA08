import requests
import json
import base64
from datetime import datetime

class FaceDeviceAPI:
    def __init__(self, base_url, device_key, secret):
        self.base_url = base_url.rstrip('/')
        self.device_key = device_key
        self.secret = secret
        
    def _make_request(self, endpoint, data=None, files=None):
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        if data is None:
            data = {}
            
        # Add required parameters
        data['deviceKey'] = self.device_key
        data['secret'] = self.secret
        
        if files:
            response = requests.post(url, data=data, files=files, headers=headers)
        else:
            response = requests.post(url, data=data, headers=headers)
            
        return response.json()
    
    def get_device_config(self):
        """Get device configuration"""
        return self._make_request('device/config')
    
    def set_device_config(self, config_data):
        """Set device configuration"""
        return self._make_request('device/config', data=config_data)
    
    def add_person(self, name, person_id=None, idcard_num=None):
        """Add a new person"""
        data = {
            'name': name,
            'id': person_id or '',
            'idcardNum': idcard_num or ''
        }
        return self._make_request('person/add', data=data)
    
    def delete_person(self, person_id):
        """Delete a person"""
        return self._make_request('person/del', data={'personId': person_id})
    
    def add_face(self, person_id, image_path, face_id=None):
        """Add face image for a person"""
        with open(image_path, 'rb') as image_file:
            img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
        
        data = {
            'personId': person_id,
            'faceId': face_id or '',
            'imgBase64': img_base64
        }
        return self._make_request('face/add', data=data)
    
    def upload_face_file(self, person_id, image_path, face_id=None):
        """Upload face image file"""
        files = {'imgFile': open(image_path, 'rb')}
        data = {
            'personId': person_id,
            'faceId': face_id or ''
        }
        return self._make_request('face/upload', data=data, files=files)
    
    def reboot_device(self):
        """Reboot the device"""
        return self._make_request('device/reboot')
    
    def open_door(self):
        """Open door remotely"""
        return self._make_request('device/openDoor')
    
    def set_identify_callback(self, callback_url):
        """Set identification callback URL"""
        return self._make_request('device/setIdentifyCallback', data={'url': callback_url})
    
    def show_message(self, message):
        """Display message on device screen"""
        return self._make_request('device/showMessage', data={'content': message})

# Example usage
if __name__ == "__main__":
    # Initialize the API client
    api = FaceDeviceAPI(
        base_url="",
        device_key="",#paste device serialo no. here
        secret=""
    )
    
    try:
        # Get device configuration
        config = api.get_device_config()
        print("Device Config:", json.dumps(config, indent=2))
        
        # Add a new person
        person_result = api.add_person("John Doe", "10001")
        print("Add Person Result:", json.dumps(person_result, indent=2))
        
        # Display message on device
        message_result = api.show_message("Hello from API!")
        print("Message Result:", json.dumps(message_result, indent=2))
        
        # Open door
        door_result = api.open_door()
        print("Open Door Result:", json.dumps(door_result, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
