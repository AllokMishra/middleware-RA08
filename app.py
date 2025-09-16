import socket
import threading
import logging
import time

# Configure logging to see output in Render's logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
PORT = 8001

def is_http_request(data):
    """Check if the received data is an HTTP request."""
    try:
        # Decode the first part of the message to see if it's an HTTP command
        message_start = data.decode('utf-8', errors='ignore').split('\r\n')[0]
        return message_start.startswith(('GET ', 'HEAD ', 'POST ', 'PUT ', 'DELETE ', 'OPTIONS '))
    except:
        return False

def handle_http_request(client_socket, data):
    """Handle an incoming HTTP request (for Render health checks)."""
    # Send a very simple HTTP 200 OK response
    http_response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    client_socket.sendall(http_response.encode())
    logger.info("Responded to HTTP health check.")
    client_socket.close()

def handle_turnstile_connection(client_socket, address):
    """Handles the incoming connection from the turnstile controller."""
    logger.info(f"Connection established from {address} - This might be the turnstile!")
    
    # Set a timeout to avoid blocking forever if it's a half-open connection
    client_socket.settimeout(30.0)
    
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                logger.info(f"Connection closed by {address}")
                break
                
            # Check if it's an HTTP request (from Render)
            if is_http_request(data):
                logger.info("Detected HTTP request, handling as health check.")
                handle_http_request(client_socket, data)
                break # Exit the loop after handling HTTP

            # If it's not HTTP, assume it's the turnstile protocol
            hex_data = ' '.join(f"{b:02x}" for b in data)
            logger.info(f"Received raw data from {address}: {hex_data}")
            
            # TODO: Here you will add the protocol parsing logic later.
            # For now, just log the data. Without a response, the turnstile will likely disconnect.
            logger.warning("Received turnstile data, but no response logic implemented yet. Connection may drop.")
            
    except socket.timeout:
        logger.warning(f"Connection from {address} timed out.")
    except Exception as e:
        logger.error(f"Error handling client {address}: {e}")
    finally:
        client_socket.close()

def start_server():
    """Starts the TCP server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    logger.info(f"Server started, listening on {HOST}:{PORT}. Waiting for turnstile connection...")
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            client_handler = threading.Thread(
                target=handle_turnstile_connection,
                args=(client_sock, address)
            )
            client_handler.start()
    except KeyboardInterrupt:
        logger.info("Server is shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()
