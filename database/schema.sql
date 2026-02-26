-- AI-MSIHPS Database Schema
-- PostgreSQL

CREATE DATABASE msihps;
\c msihps;

-- ─── Zones ────────────────────────────────────────────────────────────────────
CREATE TABLE zones (
    id          SERIAL PRIMARY KEY,
    zone_id     VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    zone_type   VARCHAR(50) CHECK (zone_type IN ('FACTORY','SEWAGE','CHEMICAL','CONFINED','BOILER')),
    location    VARCHAR(200),
    capacity    INTEGER DEFAULT 5,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ─── Sensor Readings ──────────────────────────────────────────────────────────
CREATE TABLE sensor_readings (
    id                  SERIAL PRIMARY KEY,
    zone_id             VARCHAR(50) REFERENCES zones(zone_id),
    timestamp           TIMESTAMP DEFAULT NOW(),
    -- Gas sensors (ppm)
    mq2                 FLOAT,          -- Methane, LPG, Smoke
    mq135               FLOAT,          -- NH3, NOx, Benzene, CO2
    -- Environmental
    temperature         FLOAT,          -- °C
    humidity            FLOAT,          -- %RH
    -- Structural
    vibration           FLOAT,          -- Hz
    tilt                FLOAT,          -- degrees
    liquid_level        FLOAT,          -- cm from sensor
    -- Binary
    flame_detected      BOOLEAN DEFAULT FALSE,
    sound_level         FLOAT,          -- dB
    -- AI outputs
    risk_score          FLOAT,          -- 0–100
    prediction_minutes  FLOAT,          -- minutes until unsafe (NULL if safe)
    status              VARCHAR(20)     -- SAFE / WARNING / CRITICAL
);

-- Index for fast time-series queries
CREATE INDEX idx_readings_zone_time ON sensor_readings(zone_id, timestamp DESC);
CREATE INDEX idx_readings_time ON sensor_readings(timestamp DESC);

-- ─── Workers ──────────────────────────────────────────────────────────────────
CREATE TABLE workers (
    id          SERIAL PRIMARY KEY,
    rfid_uid    VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    role        VARCHAR(50),
    department  VARCHAR(50),
    phone       VARCHAR(20),
    is_inside   BOOLEAN DEFAULT FALSE,
    last_entry  TIMESTAMP,
    last_exit   TIMESTAMP,
    photo_url   VARCHAR(200),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ─── RFID Access Log ──────────────────────────────────────────────────────────
CREATE TABLE access_log (
    id          SERIAL PRIMARY KEY,
    rfid_uid    VARCHAR(50),
    worker_id   INTEGER REFERENCES workers(id),
    zone_id     VARCHAR(50) REFERENCES zones(zone_id),
    timestamp   TIMESTAMP DEFAULT NOW(),
    action      VARCHAR(10) CHECK (action IN ('ENTRY', 'EXIT', 'DENIED')),
    risk_score  FLOAT,      -- Risk score at time of scan
    reason      VARCHAR(200)
);

-- ─── Alerts ───────────────────────────────────────────────────────────────────
CREATE TABLE alerts (
    id          SERIAL PRIMARY KEY,
    zone_id     VARCHAR(50) REFERENCES zones(zone_id),
    timestamp   TIMESTAMP DEFAULT NOW(),
    alert_type  VARCHAR(50) CHECK (alert_type IN ('GAS','FIRE','STRUCTURAL','THERMAL','GENERAL','EVACUATION')),
    severity    VARCHAR(20) CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    message     TEXT,
    risk_score  FLOAT,
    resolved    BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR(100)
);

CREATE INDEX idx_alerts_zone ON alerts(zone_id, resolved);
CREATE INDEX idx_alerts_time ON alerts(timestamp DESC);

-- ─── Supervisor Notifications ─────────────────────────────────────────────────
CREATE TABLE notifications (
    id          SERIAL PRIMARY KEY,
    alert_id    INTEGER REFERENCES alerts(id),
    channel     VARCHAR(20) CHECK (channel IN ('EMAIL','SMS','PUSH','BUZZER')),
    recipient   VARCHAR(200),
    sent_at     TIMESTAMP DEFAULT NOW(),
    status      VARCHAR(20) DEFAULT 'SENT'
);

-- ─── Sample Data ──────────────────────────────────────────────────────────────
INSERT INTO zones (zone_id, name, zone_type, location, capacity) VALUES
    ('zone_01', 'Chemical Storage A', 'CHEMICAL', 'Block A, Floor 1', 5),
    ('zone_02', 'Sewage Pit B',       'SEWAGE',   'Underground Level 2', 3),
    ('zone_03', 'Boiler Room C',      'BOILER',   'Block C, Ground Floor', 4),
    ('zone_04', 'Confined Tank D',    'CONFINED', 'Storage Yard East', 2);

INSERT INTO workers (rfid_uid, name, role, department, phone) VALUES
    ('A1B2C3D4', 'Rajan Kumar',   'Safety Officer', 'Operations',  '+91-9876543210'),
    ('E5F6G7H8', 'Priya Sharma',  'Technician',     'Maintenance', '+91-9876543211'),
    ('I9J0K1L2', 'Suresh Patel',  'Supervisor',     'Chemical',    '+91-9876543212'),
    ('M3N4O5P6', 'Kavitha Raj',   'Inspector',      'Safety',      '+91-9876543213');

-- ─── Useful Views ─────────────────────────────────────────────────────────────

-- Latest reading per zone
CREATE VIEW latest_readings AS
SELECT DISTINCT ON (zone_id)
    r.*, z.name as zone_name, z.zone_type
FROM sensor_readings r
JOIN zones z ON r.zone_id = z.zone_id
ORDER BY zone_id, timestamp DESC;

-- Active workers inside zones
CREATE VIEW workers_inside AS
SELECT w.*, al.zone_id, al.timestamp as entry_time
FROM workers w
JOIN access_log al ON w.id = al.worker_id
WHERE w.is_inside = TRUE
  AND al.action = 'ENTRY'
  AND al.timestamp = (
    SELECT MAX(timestamp) FROM access_log al2 
    WHERE al2.worker_id = w.id AND al2.action = 'ENTRY'
  );

-- Zone risk summary
CREATE VIEW zone_risk_summary AS
SELECT 
    z.zone_id, z.name, z.zone_type,
    lr.risk_score, lr.status, lr.timestamp as last_reading,
    (SELECT COUNT(*) FROM workers WHERE is_inside = TRUE) as workers_inside,
    (SELECT COUNT(*) FROM alerts WHERE zone_id = z.zone_id AND resolved = FALSE) as active_alerts
FROM zones z
LEFT JOIN latest_readings lr ON z.zone_id = lr.zone_id
WHERE z.is_active = TRUE;