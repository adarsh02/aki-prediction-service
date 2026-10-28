import unittest
from unittest.mock import Mock, patch
from datetime import datetime

from receiver.mllp import (
    MLLPReceiver,
    START_BLOCK,
    END_BLOCK,
    CARRIAGE_RETURN,
)


class TestMLLPReceiver(unittest.TestCase):

    def setUp(self):
        self.receiver = MLLPReceiver(
            mllp_address="localhost:1234"
        )

        self.mock_socket = Mock()
        self.mock_socket.recv = Mock()
        self.mock_socket.sendall = Mock()
        self.mock_socket.close = Mock()

    # -------------------------
    # connect()
    # -------------------------

    @patch("socket.create_connection")
    def test_connect_creates_socket(self, mock_create_conn):
        mock_create_conn.return_value = self.mock_socket

        self.receiver.connect()

        mock_create_conn.assert_called_once_with(("localhost", 1234))
        self.assertEqual(self.receiver.sock, self.mock_socket)

    # -------------------------
    # receive_message()
    # -------------------------

    def test_receive_message_strips_mllp_framing(self):
        hl7 = b"MSH|^~\\&|TEST\rPID|1\r"
        framed = START_BLOCK + hl7 + END_BLOCK + CARRIAGE_RETURN

        self.mock_socket.recv.side_effect = [framed]
        self.receiver.sock = self.mock_socket

        msg = self.receiver.receive_message()

        self.assertEqual(msg, hl7.decode("utf-8"))

    # -------------------------
    # send_ack()
    # -------------------------

    @patch("receiver.mllp.datetime")
    def test_send_ack_sends_framed_ack(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 1, 1, 0, 0, 0)

        self.receiver.sock = self.mock_socket
        self.receiver.send_ack("AA")

        self.mock_socket.sendall.assert_called_once()
        sent = self.mock_socket.sendall.call_args[0][0]

        self.assertTrue(sent.startswith(START_BLOCK))
        self.assertTrue(sent.endswith(END_BLOCK + CARRIAGE_RETURN))
        self.assertIn(b"MSA|AA", sent)
