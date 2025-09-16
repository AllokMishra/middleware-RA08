import socket
import threading
import logging
import time
from queue import Queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AccessControllerServer:
    def __init__(self, host='0.0.0.0', port=8001):
        self.host = host
        self.port = port
        self.server_socket = None
        self.controller_conn = None
        self.controller_addr = None
        self.running = False
        self.command_queue = Queue()
        
        # Protocol constants
        self.STX = 0x02
        self.ETX = 0x03
        self.RAND = 0xA0  # Default random value for commands we send
        
    def calculate_checksum(self, data):
        """Calculate XOR checksum for the given bytes (excluding STX and ETX)"""
        if not data:
            return 0
            
        checksum = data[0]
        for byte in data[1:]:
            checksum ^= byte
        return checksum
    
    def build_command_frame(self, command, data=None, door=0):
        """
        Build a command frame according to the protocol specification
        
        Args:
            command: The command byte
            data: Optional data bytes
            door: Door number (0-4)
        
        Returns:
            bytes: The complete frame to send
        """
        if data is None:
            data = b''
            
        # Calculate data length
        data_length = len(data)
        length_l = data_length & 0xFF  # Low byte
        length_h = (data_length >> 8) & 0xFF  # High byte
        
        # Build the main part of the frame (without checksum and ETX)
        frame_data = bytearray()
        frame_data.append(self.STX)
        frame_data.append(self.RAND)
        frame_data.append(command)
        frame_data.append(0xFF)  # Address (ignored)
        frame_data.append(door)  # Door number
        frame_data.append(length_l)
        frame_data.append(length_h)
        frame_data.extend(data)
        
        # Calculate checksum for the frame (excluding STX and ETX)
        # The checksum covers from RAND to the end of data
        checksum_data = frame_data[1:]  # Everything after STX
        cs = self.calculate_checksum(checksum_data)
        
        # Append checksum and ETX
        frame_data.append(cs)
        frame_data.append(self.ETX)
        
        return bytes(frame_data)
    
    def parse_frame(self, data):
        """
        Parse a received frame and validate its structure
        
        Args:
            data: The received bytes
            
        Returns:
            dict: Parsed frame information or None if invalid
        """
        # Basic validation
        if len(data) < 10:  # Minimum frame size (without data)
            logger.warning(f"Frame too short: {len(data)} bytes")
            return None
            
        if data[0] != self.STX or data[-1] != self.ETX:
            logger.warning("Invalid STX or ETX")
            return None
            
        # Extract header fields
        rand = data[1]
        command = data[2]
        address = data[3]
        door = data[4]
        length_l = data[5]
        length_h = data[6]
        data_length = length_l + (length_h << 8)
        
        # Validate frame length
        expected_length = 10 + data_length  # Header(8) + CS(1) + ETX(1) = 10
        if len(data) != expected_length:
            logger.warning(f"Frame length mismatch: expected {expected_length}, got {len(data)}")
            return None
            
        # Extract data section
        data_start = 7
        data_end = data_start + data_length
        frame_data = data[data_start:data_end]
        
        # Extract checksum
        received_cs = data[data_end]
        
        # Calculate expected checksum (from RAND to end of data)
        checksum_data = data[1:data_end]
        expected_cs = self.calculate_checksum(checksum_data)
        
        if received_cs != expected_cs:
            logger.warning(f"Checksum mismatch: expected {expected_cs:02X}, got {received_cs:02X}")
            return None
            
        # Return parsed frame
        return {
            'rand': rand,
            'command': command,
            'address': address,
            'door': door,
            'length': data_length,
            'data': frame_data,
            'cs': received_cs
        }
    
    def handle_heartbeat(self, frame):
        """Handle heartbeat command (0x56) from controller"""
        logger.info("Received heartbeat command")
        
        # Response to heartbeat: 2 bytes of customer code (0x00, 0x00)
        response_data = bytes([0x00, 0x00])
        response_frame = self.build_command_frame(0x56, response_data, door=0)
        
        try:
            if self.controller_conn:
                self.controller_conn.send(response_frame)
                logger.info("Sent heartbeat response")
        except Exception as e:
            logger.error(f"Error sending heartbeat response: {e}")
    
    def handle_swipe_record(self, frame):
        """Handle swipe card record (0x53) from controller"""
        logger.info("Received swipe card record")
        
        # Parse the record data according to protocol specification
        # Data structure: 4B card no, 6B time, 1B type, 1B door, 1B more records, 1B serial no, 1B data type, 1B card status
        if len(frame['data']) >= 15:  # Minimum expected data length
            card_no = int.from_bytes(frame['data'][0:4], byteorder='little')
            
            # Time: year, month, day, hour, minute, second
            time_data = frame['data'][4:10]
            year = 2000 + time_data[5]  # Year needs to add 2000
            month = time_data[4]
            day = time_data[3]
            hour = time_data[2]
            minute = time_data[1]
            second = time_data[0]
            
            record_type = frame['data'][10]
            door = frame['data'][11]
            more_records = frame['data'][12]
            serial_no = frame['data'][13]
            data_type = frame['data'][14]
            card_status = frame['data'][15] if len(frame['data']) > 15 else 0
            
            # Log the swipe record
            logger.info(
                f"Swipe record - Card: {card_no}, "
                f"Time: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}, "
                f"Type: {record_type}, Door: {door}"
            )
            
            # Send response with the received serial number
            response_data = bytes([serial_no])
            response_frame = self.build_command_frame(0x53, response_data, door=0)
            
            try:
                if self.controller_conn:
                    self.controller_conn.send(response_frame)
                    logger.info("Sent swipe record response")
            except Exception as e:
                logger.error(f"Error sending swipe record response: {e}")
        else:
            logger.warning(f"Invalid swipe record data length: {len(frame['data'])}")
    
    def handle_alarm_record(self, frame):
        """Handle alarm record (0x54) from controller"""
        logger.info("Received alarm record")
        
        # Parse the alarm data
        if len(frame['data']) >= 10:  # Minimum expected data length
            # Time: year, month, day, hour, minute, second
            time_data = frame['data'][0:6]
            year = 2000 + time_data[5]  # Year needs to add 2000
            month = time_data[4]
            day = time_data[3]
            hour = time_data[2]
            minute = time_data[1]
            second = time_data[0]
            
            record_type = frame['data'][6]
            door = frame['data'][7]
            more_records = frame['data'][8]
            serial_no = frame['data'][9]
            
            # Log the alarm record
            logger.info(
                f"Alarm record - "
                f"Time: {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}, "
                f"Type: {record_type}, Door: {door}"
            )
            
            # Send response with the received serial number
            response_data = bytes([serial_no])
            response_frame = self.build_command_frame(0x54, response_data, door=0)
            
            try:
                if self.controller_conn:
                    self.controller_conn.send(response_frame)
                    logger.info("Sent alarm record response")
            except Exception as e:
                logger.error(f"Error sending alarm record response: {e}")
        else:
            logger.warning(f"Invalid alarm record data length: {len(frame['data'])}")
    
    def open_door(self, door=1):
        """Send command to open the specified door"""
        logger.info(f"Sending open door command for door {door}")
        
        # Build open door command (0x2C) with no data
        open_door_frame = self.build_command_frame(0x2C, door=door)
        
        try:
            if self.controller_conn:
                self.controller_conn.send(open_door_frame)
                logger.info("Open door command sent")
                return True
        except Exception as e:
            logger.error(f"Error sending open door command: {e}")
        
        return False
    
    def handle_controller_connection(self, conn, addr):
        """Handle communication with a connected controller"""
        logger.info(f"Controller connected from {addr}")
        self.controller_conn = conn
        self.controller_addr = addr
        
        try:
            while self.running:
                # Receive data
                data = conn.recv(1024)
                if not data:
                    logger.info("Controller disconnected")
                    break
                
                # Log received data
                logger.info(f"Received: {data.hex()}")
                
                # Parse the frame
                frame = self.parse_frame(data)
                if not frame:
                    logger.warning("Failed to parse frame")
                    continue
                
                # Handle different commands
                if frame['command'] == 0x56:  # Heartbeat
                    self.handle_heartbeat(frame)
                elif frame['command'] == 0x53:  # Swipe record
                    self.handle_swipe_record(frame)
                elif frame['command'] == 0x54:  # Alarm record
                    self.handle_alarm_record(frame)
                else:
                    logger.info(f"Received unhandled command: 0x{frame['command']:02X}")
                
                # Process any queued commands
                try:
                    while not self.command_queue.empty():
                        cmd = self.command_queue.get_nowait()
                        if cmd == 'open_door':
                            self.open_door()
                except Exception as e:
                    logger.error(f"Error processing command queue: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling controller connection: {e}")
        finally:
            conn.close()
            self.controller_conn = None
            self.controller_addr = None
            logger.info("Controller connection closed")
    
    def start_server(self):
        """Start the TCP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.running = True
            logger.info(f"Server started on {self.host}:{self.port}")
            
            while self.running:
                logger.info("Waiting for controller connection...")
                try:
                    conn, addr = self.server_socket.accept()
                    
                    # Handle the connection in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_controller_connection,
                        args=(conn, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except OSError as e:
                    if self.running:
                        logger.error(f"Accept error: {e}")
                    break
                
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop_server()
    
    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.controller_conn:
            try:
                self.controller_conn.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("Server stopped")
    
    def trigger_open_door(self):
        """Queue an open door command to be sent to the controller"""
        self.command_queue.put('open_door')
        logger.info("Open door command queued")

def main():
    """Main function to run the server"""
    server = AccessControllerServer(host='0.0.0.0', port=8001)
    
    try:
        # Start the server
        print("Starting Access Controller Server...")
        server.start_server()
                
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server.stop_server()

if __name__ == "__main__":
    main()
