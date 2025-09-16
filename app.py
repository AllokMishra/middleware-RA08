import socket
import threading
import logging

# Configure logging to see output in Render's logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'  # Listen on all available network interfaces
PORT = 8001        # Must match the port set in the turnstile config

def handle_client_connection(client_socket, address):
    """Handles the incoming connection from the turnstile controller."""
    logger.info(f"Connection established from {address}")
    
    try:
        # Keep the connection open and read data
        while True:
            data = client_socket.recv(1024)
            if not data:
                # If no data is received, the client has disconnected
                logger.info(f"Connection closed by {address}")
                break
                
            # Log the raw bytes received in hexadecimal format
            hex_data = ' '.join(f"{b:02x}" for b in data)
            logger.info(f"Received from {address}: {hex_data}")
            
            # TODO: In the full version, we would parse the data here,
            # calculate the correct response, and send it back.
            # For now, we just log it.
            
    except Exception as e:
        logger.error(f"Error handling client {address}: {e}")
    finally:
        client_socket.close()

def start_server():
    """Starts the TCP server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # This option allows the port to be reused quickly after a restart
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5) # Allow a queue of up to 5 connections
    logger.info(f"Server started, listening on {HOST}:{PORT}")
    
    try:
        while True:
            client_sock, address = server_socket.accept()
            # Start a new thread to handle each client (though you likely only have one turnstile)
            client_handler = threading.Thread(
                target=handle_client_connection,
                args=(client_sock, address)
            )
            client_handler.start()
    except KeyboardInterrupt:
        logger.info("Server is shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()
