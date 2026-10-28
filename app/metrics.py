from prometheus_client import Counter, Histogram, start_http_server

# =========================================================
# 1. INGESTION & CONNECTIVITY METRICS (System Health)
# =========================================================

mllp_reconnections_total = Counter(
    "mllp_reconnections_total",
    "Total MLLP reconnections. Spikes indicate simulator restarts or network drops."
)

mllp_read_errors_total = Counter(
    "mllp_read_errors_total",
    "Errors encountered when reading from the MLLP socket (e.g., connection reset by peer)."
)

# =========================================================
# 2. MESSAGE PARSING & VALIDATION METRICS (Data Integrity)
# =========================================================

messages_total = Counter(
    "messages_total",
    "Total HL7 messages received.",
    ["message_type"]  # e.g. ADT, ORU
)

malformed_messages_total = Counter(
    "malformed_messages_total",
    "HL7 messages that failed structural validation."
)

# =========================================================
# 3. DATABASE METRICS (State Management)
# =========================================================

db_operations_errors_total = Counter(
    "db_operations_errors_total",
    "Total failed SQLite transactions (commits or rollbacks).",
    ["operation_type"]
)

# =========================================================
# 4. ML INPUT & OUTPUT METRICS (Model Health)
# =========================================================

blood_tests_total = Counter(
    "blood_tests_total",
    "Total blood test results received."
)

blood_test_value_distribution = Histogram(
    "blood_test_value_distribution",
    "Distribution of blood test values (creatinine).",
    buckets=[0, 50, 100, 150, 200, 300, 500, 1000]
)

aki_predictions_total = Counter(
    "aki_predictions_total",
    "Total AKI predictions made by the inference engine."
)

inference_errors_total = Counter(
    "inference_errors_total",
    "Total failed inference attempts."
)

# =========================================================
# 5. EGRESS & ALERTING METRICS (Downstream Reliability)
# =========================================================

pager_requests_total = Counter(
    "pager_requests_total",
    "Total HTTP requests sent to the pager service.",
    ["status_code"]  # e.g. '200', '404', '500', 'connection_error'
)

pager_retries_total = Counter(
    "pager_retries_total",
    "Total retry attempts for pager service failures.",
    ["status_code"]
)

# =========================================================
# 6. PERFORMANCE SLA METRICS (System Latency)
# =========================================================

processing_latency_seconds = Histogram(
    "processing_latency_seconds",
    "End-to-end processing latency from message receipt to pager alert.",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0]
)

# =========================================================
# SERVER INITIALIZATION
# =========================================================

def start_metrics_server(port: int = 8000) -> None:
    """
    Starts the embedded Prometheus HTTP server.
    Exposes metrics at http://localhost:<port>/metrics
    """
    start_http_server(port)