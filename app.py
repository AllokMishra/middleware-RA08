import socket
import threading
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
PORT = 8001

def calculate_checksum(data_bytes):
    """Calculate XOR checksum for a list of bytes."""
    checksum = 0
    for byte in data_bytes:
        checksum ^= byte
    return checksum

def build_response_frame(command, data=None, door=0):
    """Build a valid response frame based on the protocol."""
    frame_parts = []
    # Header
    frame_parts.append(0x02)  # STX
    frame_parts.append(0xA0)  # Rand
    frame_parts.append(command)  # Command
    frame_parts.append(0xFF)  # Address
    frame_parts.append(door)   # Door

    # Handle data length (LOW byte first, then HIGH byte for commands we send)
    if data is None:
        data_bytes = []
        frame_parts.append(0x00)  # LengthL
        frame_parts.append(0x00)  # LengthH
    else:
        data_bytes = list(data)
        data_length = len(data_bytes)
        frame_parts.append(data_length & 0xFF)  # LengthL (low byte)
        frame_parts.append((data_length >> 8) & 0xFF)  # LengthH (high byte)

    # Add data bytes if any
    frame_parts.extend(data_bytes)

    # Calculate checksum up to this point
    checksum = calculate_checksum(frame_parts)
    frame_parts.append(checksum)

    # End of frame
    frame_parts.append(0x03)  # ETX

    return bytes(frame_parts)

def handle_heartbeat(data):
    """Handle heartbeat command (0x56) from controller."""
    # The heartbeat response requires 2 bytes of customer code (often 0x00)
    response_data = bytes([0x00, 0x00])  # Customer code high & low byte
    response_frame = build_response_frame(0x56, data=response_data)
    return response_frame

def handle_swipe_record(data):
    """Handle swipe record command (0x53) from controller."""
    # The response must echo back the record serial number (7th byte of data)
    if len(data) >= 7:
        record_serial = data[6:7]  # Get the serial number byte
        response_frame = build_response_frame(0x53, data=record_serial)
        return response_frame
    return None

def handle_client_connection(client_socket, address):
    """Handle the incoming connection from the turnstile controller."""
    logger.info(f"Turnstile connection established from {address}")
    
    try:
        while True:
            # Read data from the controller
            data = client_socket.recv(1024)
            if not data:
                logger.info(f"Connection closed by {address}")
                break

            # Log raw received data
            hex_data = ' '.join(f"{b:02x}" for b in data)
            logger.info(f"Received from {address}: {hex_data}")

            # Validate frame structure (must start with 0x02 and end with 0x03)
            if data[0] != 0x02 or data[-1] != 0x03:
                logger.warning(f"Invalid frame structure from {address}")
                continue

            # Verify checksum
            received_checksum = data[-2]
            calculated_checksum = calculate_checksum(data[0:-2])
            
            if received_checksum != calculated_checksum:
                logger.warning(f"Checksum mismatch from {address}. Received: {received_checksum:02x}, Calculated: {calculated_checksum:02x}")
                continue

            # Extract command byte (3rd byte in frame)
            command = data[2]
            # Extract data portion (between header and checksum)
            data_length = (data[6] << 8) | data[5]  # LengthH + LengthL
            data_start = 7  # Header is 7 bytes
            data_end = data_start + data_length
            payload = data[data_start:data_end]

            # Handle different commands
            if command == 0x56:  # Heartbeat
                logger.info("Handling heartbeat command (0x56)")
                response = handle_heartbeat(payload)
                if response:
                    client_socket.sendall(response)
                    logger.info("Sent heartbeat response")

            elif command == 0x53:  # Swipe record
                logger.info("Handling swipe record command (0x53)")
                response = handle_swipe_record(payload)
                if response:
                    client_socket.sendall(response)
                    logger.info("Sent swipe record response")

            elif command == 0x54:  # Alarm record
                logger.info("Handling alarm record command (0x54)")
                # Respond similarly to swipe record
                if len(payload) >= 6:
                    record_serial = payload[5:6]
                    response = build_response_frame(0x54, data=record_serial)
                    client_socket.sendall(response)
                    logger.info("Sent alarm record response")

            else:
                logger.warning(f"Unknown command received: 0x{command:02x}")

    except socket.timeout:
        logger.warning(f"Connection from {address} timed out")
    except socket.error as e:
        logger.error(f"Socket error with {address}: {e}")
    except Exception as e:
        logger.error(f"Error handling client {address}: {e}")
    finally:
        client_socket.close()
        logger.info(f"Connection to {address} closed")

def start_server():
    """Start the TCP server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Server started and listening on {HOST}:{PORT}")

    try:
        while True:
            client_sock, address = server_socket.accept()
            client_handler = threading.Thread(
                target=handle_client_connection,
                args=(client_sock, address),
                daemon=True
            )
            client_handler.start()
            logger.info(f"Started handler for {address}")
    except KeyboardInterrupt:
        logger.info("Server shutting down")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()
