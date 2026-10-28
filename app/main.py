import os
import logging
import signal
import time
from receiver.mllp import MLLPReceiver
from hl7.handler import MessageHandler
from controller.controller import Controller
from db.db_manager import DBManager
from inference.engine import AKIInferenceEngine
from config import init_logging
from db.bootstrap import init_db
from metrics import start_metrics_server, processing_latency_seconds

class GracefulShutdown(SystemExit):
    """Custom exception raised on SIGINT or SIGTERM for graceful exit."""
    pass


def handle_exit(signum: int, frame) -> None:
    """Signal handler that raises a graceful shutdown exception."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    raise GracefulShutdown()


# Register signals once
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


def main() -> None:
    """
    Initialize components, connect to MLLP, and process HL7 messages in a loop.
    Gracefully handles shutdown signals and ensures socket closure.
    """

    logger, controller, message_handler, receiver = init_app()

    try:
        receiver.connect()

        while True:
            msg = receiver.receive_message()
            if not msg:
                continue
            
            start_time = time.time()
            ack_code, prediction, mrn, test_time = message_handler.handle(msg)
            logger.info(f"Current MRN: {mrn}, Test time: {test_time}")

            if prediction:
                controller.page_aki(mrn, test_time)

            receiver.send_ack(ack_code)
            duration = time.time() - start_time
            processing_latency_seconds.observe(duration)
            

    except GracefulShutdown:
        logger.error("Shutting down gracefully due to signal.")
    except Exception as e:
        logger.critical(f"Unexpected error in main loop: {e}", exc_info=True)
    finally:
        receiver.stop()
        logger.info("Receiver stopped. Exiting.")

def init_app():
    try:
        init_logging()
        start_metrics_server()
        init_db()
        logger = logging.getLogger(__name__)
        logger.info("Application starting")

        mllp_address = os.getenv("MLLP_ADDRESS", "localhost:8440")
        pager_address = os.getenv("PAGER_ADDRESS", "localhost:8441")

        db_manager = DBManager()
        inference_engine = AKIInferenceEngine()
        controller = Controller(db_manager=db_manager, inference_engine=inference_engine, pager_address=pager_address)
        message_handler = MessageHandler(controller)
        receiver = MLLPReceiver(mllp_address)
        
        return logger, controller, message_handler, receiver
    except Exception as e:
        print(f"Unknown Exception: {e}")
        

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error running main: {e}")
