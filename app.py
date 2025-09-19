import socket
import time
import struct
from datetime import datetime

class AccessControllerClient:
    def __init__(self, host, port=6000):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        
    def connect(self):
        """Establish connection to the access controller"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print(f"Connected to access controller at {self.host}:{self.port}")
            
            # Start a thread to listen for unsolicited messages from controller
            self.listening = True
            self.listener_thread = threading.Thread(target=self._listen_for_messages)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close the connection"""
        self.listening = False
        if self.sock:
            self.sock.close()
        self.connected = False
        print("Disconnected from access controller")
    
    def _calculate_checksum(self, data):
        """Calculate XOR checksum for the data"""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum
    
    def _create_command_frame(self, command, door=0, data=b''):
        """Create a command frame with proper structure"""
        # Frame structure: STX, Rand, Command, Address, Door, LengthL, LengthH, Data, CS, ETX
        frame = bytearray()
        frame.append(0x02)  # STX
        frame.append(random.randint(0, 255))  # Random byte
        frame.append(command)  # Command
        frame.append(0xFF)  # Address (default)
        frame.append(door)  # Door number
        
        # Data length (little endian)
        length = len(data)
        frame.append(length & 0xFF)  # LengthL
        frame.append((length >> 8) & 0xFF)  # LengthH
        
        # Add data if any
        if data:
            frame.extend(data)
        
        # Calculate checksum (XOR of all bytes except STX, CS, and ETX)
        checksum_data = frame[1:]  # All bytes after STX
        cs = self._calculate_checksum(checksum_data)
        frame.append(cs)  # Checksum
        
        frame.append(0x03)  # ETX
        
        return bytes(frame)
    
    def _parse_response(self, response):
        """Parse a response from the controller"""
        if len(response) < 10:  # Minimum frame size
            raise ValueError("Response too short")
        
        if response[0] != 0x02 or response[-1] != 0x03:
            raise ValueError("Invalid frame format")
        
        # Verify checksum
        received_cs = response[-2]
        calculated_cs = self._calculate_checksum(response[1:-2])
        if received_cs != calculated_cs:
            raise ValueError("Checksum mismatch")
        
        # Extract response data
        command = response[2]
        door = response[4]
        lengthL = response[5]
        lengthH = response[6]
        data_length = lengthL + (lengthH << 8)
        
        if data_length > 0:
            data = response[7:7+data_length]
        else:
            data = b''
        
        return command, door, data
    
    def _listen_for_messages(self):
        """Listen for unsolicited messages from controller (state, records, etc.)"""
        buffer = b''
        while self.listening and self.connected:
            try:
                data = self.sock.recv(1024)
                if not data:
                    self.connected = False
                    break
                
                buffer += data
                
                # Process complete frames in buffer
                while len(buffer) >= 2:
                    # Find STX
                    stx_pos = buffer.find(b'\x02')
                    if stx_pos == -1:
                        buffer = b''
                        break
                    
                    # Find ETX after STX
                    etx_pos = buffer.find(b'\x03', stx_pos)
                    if etx_pos == -1:
                        break  # Incomplete frame, wait for more data
                    
                    frame = buffer[stx_pos:etx_pos+1]
                    buffer = buffer[etx_pos+1:]
                    
                    try:
                        command, door, data = self._parse_response(frame)
                        self._handle_unsolicited_message(command, door, data)
                    except ValueError as e:
                        print(f"Error parsing frame: {e}")
                        
            except Exception as e:
                if self.listening:
                    print(f"Error in listener: {e}")
                break
    
    def _handle_unsolicited_message(self, command, door, data):
        """Handle unsolicited messages from controller"""
        if command == 0x56:  # State/heartbeat
            self._handle_state_message(data)
        elif command == 0x53:  # Swipe card record
            self._handle_swipe_record(data)
        elif command == 0x54:  # Alarm record
            self._handle_alarm_record(data)
        elif command == 0x52:  # Card state record
            self._handle_card_state_record(data)
        else:
            print(f"Received unsolicited message: command=0x{command:02x}, door={door}")
    
    def _handle_state_message(self, data):
        """Handle state/heartbeat message (0x56)"""
        if len(data) < 15:  # Minimum state data length
            print("State message too short")
            return
        
        # Parse state data according to protocol
        address = data[0]
        time_data = data[1:7]  # Year, month, day, hour, minute, second
        door_state = data[7]
        cards_per_packet = data[8]
        unused = data[9]
        function_flags = data[10]
        controller_type = data[11]
        lock_status = data[12]
        # Additional fields would be parsed here
        
        # Convert time
        year = time_data[0] + 2000
        month = time_data[1]
        day = time_data[2]
        hour = time_data[3]
        minute = time_data[4]
        second = time_data[5]
        
        print(f"Controller state: time={year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}, "
              f"door_state=0x{door_state:02x}, controller_type={controller_type}")
        
        # Send response to controller (customer code)
        response_data = bytes([0x00, 0x00])  # Default customer code
        response_frame = self._create_command_frame(0x56, 0, response_data)
        self._send_frame(response_frame)
    
    def _handle_swipe_record(self, data):
        """Handle swipe card record (0x53)"""
        if len(data) < 14:  # Minimum record length
            print("Swipe record too short")
            return
        
        # Parse record data
        card_no = struct.unpack('<I', data[0:4])[0]  # 4-byte card number (little endian)
        time_data = data[4:10]  # Year, month, day, hour, minute, second
        event_type = data[10]
        door = data[11]
        has_more_records = data[12]
        record_serial = data[13]
        
        # Convert time
        year = time_data[5] + 2000  # Year is last byte in time data
        month = time_data[4]
        day = time_data[3]
        hour = time_data[2]
        minute = time_data[1]
        second = time_data[0]
        
        print(f"Swipe record: card={card_no}, time={year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}, "
              f"event=0x{event_type:02x}, door={door}")
        
        # Send response to controller (record serial number)
        response_data = bytes([record_serial])
        response_frame = self._create_command_frame(0x53, 0, response_data)
        self._send_frame(response_frame)
    
    def _handle_alarm_record(self, data):
        """Handle alarm record (0x54)"""
        # Similar implementation to swipe record handling
        print("Received alarm record")
        # Send response with record serial number
        if len(data) >= 10:
            record_serial = data[9]  # Position of serial number in alarm record
            response_data = bytes([record_serial])
            response_frame = self._create_command_frame(0x54, 0, response_data)
            self._send_frame(response_frame)
    
    def _handle_card_state_record(self, data):
        """Handle card state record (0x52)"""
        if len(data) >= 5:
            card_index = struct.unpack('<H', data[0:2])[0]  # 2-byte card index (little endian)
            card_state = data[2]
            record_serial = data[3]
            has_more = data[4]
            
            print(f"Card state record: index={card_index}, state=0x{card_state:02x}")
            
            # Send response to controller
            response_data = bytes([record_serial])
            response_frame = self._create_command_frame(0x52, 0, response_data)
            self._send_frame(response_frame)
    
    def _send_frame(self, frame):
        """Send a frame to the controller"""
        try:
            self.sock.sendall(frame)
            return True
        except Exception as e:
            print(f"Error sending frame: {e}")
            self.connected = False
            return False
    
    def send_command(self, command, door=0, data=b''):
        """Send a command to the controller and wait for response"""
        if not self.connected:
            print("Not connected to controller")
            return None
        
        frame = self._create_command_frame(command, door, data)
        
        if not self._send_frame(frame):
            return None
        
        # For commands that expect a response, wait for it
        if command not in [0x56, 0x53, 0x54, 0x52]:  # These are unsolicited messages
            try:
                # Wait for response
                response = self.sock.recv(1024)
                if response:
                    return self._parse_response(response)
            except socket.timeout:
                print("Timeout waiting for response")
            except Exception as e:
                print(f"Error receiving response: {e}")
        
        return None
    
    # Specific command implementations
    def open_door(self, door):
        """Send open door command (0x2C)"""
        print(f"Opening door {door}")
        return self.send_command(0x2C, door, bytes([door]))
    
    def close_door(self, door):
        """Send close door command (0x2E)"""
        print(f"Closing door {door}")
        return self.send_command(0x2E, door, bytes([door]))
    
    def set_time(self):
        """Send time synchronization command (0x07)"""
        now = datetime.now()
        time_data = bytes([
            now.second,  # Second
            now.minute,  # Minute
            now.hour,    # Hour (24h)
            now.isoweekday() % 7 + 1,  # Week (1-7, 1=Monday)
            now.day,     # Day
            now.month,   # Month
            now.year - 2000  # Year (offset from 2000)
        ])
        print("Synchronizing time with controller")
        return self.send_command(0x07, 0, time_data)
    
    def reset_controller(self):
        """Send reset controller command (0x04)"""
        print("Resetting controller")
        return self.send_command(0x04)

# Example usage
if __name__ == "__main__":
    import threading
    
    # Replace with your controller's IP address
    CONTROLLER_IP = "192.168.0.112"
    
    client = AccessControllerClient(CONTROLLER_IP)
    
    if client.connect():
        try:
            # Synchronize time with controller
            client.set_time()
            
            # Open door 1
            client.open_door(1)
            
            # Keep the connection alive to receive unsolicited messages
            print("Listening for controller messages...")
            time.sleep(30)  # Listen for 30 seconds
            
        except KeyboardInterrupt:
            print("Disconnecting...")
        finally:
            client.disconnect()
    else:
        print("Failed to connect to controller")
