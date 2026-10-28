-- =========================
-- Patients (identity + current status)
-- =========================
CREATE TABLE IF NOT EXISTS patients (
    mrn TEXT PRIMARY KEY,
    name TEXT,
    dob TEXT,
    sex TEXT,
    admission_status TEXT CHECK (admission_status IN ('ADMITTED', 'DISCHARGED')),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Lab Results (core inference driver)
-- =========================
CREATE TABLE IF NOT EXISTS lab_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mrn INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    test_time TIMESTAMP NOT NULL,
    value REAL NOT NULL,
    processing_status TEXT DEFAULT 'PROCESSED',
    UNIQUE(mrn , test_time)
    -- inferred INTEGER DEFAULT 0,
    -- FOREIGN KEY (mrn) REFERENCES patients(mrn)
);

CREATE INDEX IF NOT EXISTS idx_lab_mrn_time ON lab_results(mrn, test_time);

CREATE INDEX IF NOT EXISTS idx_pending_labs ON lab_results(mrn) WHERE processing_status = 'PENDING_ADMIT';