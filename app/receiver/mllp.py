import socket
import time
from datetime import datetime
import logging

from metrics import mllp_reconnections_total, mllp_read_errors_total

logger = logging.getLogger(__name__)

START_BLOCK = b'\x0b'
END_BLOCK = b'\x1c'
CARRIAGE_RETURN = b'\x0d'


class MLLPReceiver:
    """
    TCP-based MLLP receiver for HL7 messages with automatic reconnect.
    """

    def __init__(self, mllp_address: str, reconnect_delay: int = 5):
        host, port = mllp_address.split(":")
        self.host: str = host
        self.recv_port: int = int(port)
        self.sock: socket.socket | None = None
        self.running: bool = False
        self.reconnect_delay: int = reconnect_delay
        self.has_connected_once = False

    def connect(self) -> None:
        """
        Establish a TCP connection to the MLLP sender, retrying on failure.
        """
        while True:
            try:
                self.sock = socket.create_connection((self.host, self.recv_port))
                # sends a keepalive message on the connection once every 10 mins
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 600)    # 10 min idle
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)    # 10 sec between probes
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)       # 3 probes
                self.running = True
                logger.info(f"Connected to MLLP server at {self.host}:{self.recv_port}")
                
                if self.has_connected_once:
                    mllp_reconnections_total.inc()
                
                self.has_connected_once = True
                
                return
            except socket.gaierror as e:
                logger.warning(f"DNS resolution failed: {e}. Retrying in 5 seconds...")
            except (socket.error, ConnectionRefusedError) as e:
                logger.warning(f"MLLP connection failed: {e}. Retrying in {self.reconnect_delay}s...")
            
            time.sleep(self.reconnect_delay)

    def is_running(self) -> bool:
        """
        Helper function used to check if the socket connection is open
        
        Returns:
            Boolean: True if open, else False
        """
        return self.running

    def receive_message(self) -> str:
        """
        Receive one complete HL7 message from the MLLP socket.

        Accumulates incoming TCP chunks until the END_BLOCK + CARRIAGE_RETURN
        sequence is detected. Handles partial or split messages and automatically
        reconnects if the connection drops.
        
        Returns:
            The complete HL7 message as a decoded string.
        """
        buffer = b""

        while True:
            try:
                chunk = self.sock.recv(1024)
                if not chunk:
                    # ignore zero length pkt
                    # assumes that the network will never randomly drop the connection
                    # and that the simulator will always gracefully shutdown
                    raise ConnectionResetError("Socket closed by peer")

                buffer += chunk

                # If END_BLOCK + CARRIAGE_RETURN is in the accumulated buffer then entire message must have been read
                # assumed here that multiple mllp messages cannot be in one tcp packet.
                # assumed each tcp packet contains either the entire of part of an mllp packet
                if END_BLOCK + CARRIAGE_RETURN in buffer:
                    start = 1 if buffer.startswith(START_BLOCK) else 0
                    end = buffer.index(END_BLOCK + CARRIAGE_RETURN)
                    message = buffer[start:end]

                    logger.info("Received message from MLLP server")
                    logger.debug(f"Message: {message!r}")
                    return message.decode("utf-8")

            except (ConnectionResetError, socket.error) as e:
                logger.warning(f"Connection lost: {e}. Attempting to reconnect...")
                self.stop()
                self.connect()
                # reset buffer after reconnect to avoid partial/corrupted messages
                buffer = b""


    def send_ack(self, ack_code: str, max_retx: int = 3) -> None:
        """
        Send an HL7 ACK message to the sender with automatic retries if the connection fails.

        Args:
            ack_code: HL7 acknowledgment code ('AA', 'AE', etc.)
            max_retx: Maximum number of attempts to send the ACK (default 3)
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        ack_message = f"MSH|^~\\&|||||{timestamp}||ACK|||2.5\rMSA|{ack_code}\r"

        attempts = 0
        while attempts < max_retx:
            attempts += 1
            try:
                self.sock.sendall(START_BLOCK + ack_message.encode("utf-8") + END_BLOCK + CARRIAGE_RETURN)
                logger.info(f"ACK sent successfully (attempt {attempts})")
                return  # success
            except (socket.error, AttributeError) as e:
                logger.warning(f"Attempt {attempts} failed to send ACK: {e}")

                if attempts < max_retx:
                    logger.warning("Reconnecting socket before retrying ACK...")
                    self.stop()
                    self.connect()
                else:
                    logger.error(f"Failed to send ACK after {max_retx} attempts. Giving up.")



    def stop(self) -> None:
        """
        Close the socket and mark receiver as not running.
        """
        self.running = False
        logger.info("MLLP server connection closed")
        if self.sock:
            self.sock.close()
            self.sock = None
