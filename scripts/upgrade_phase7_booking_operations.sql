-- Run against the explicitly selected database. No USE and no data rewrites.
CREATE TABLE IF NOT EXISTS court_block (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  court_id BIGINT NOT NULL,
  reserve_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  reason VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_by BIGINT NOT NULL,
  released_by BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  released_at DATETIME NULL,
  KEY idx_block_court_date (court_id, reserve_date, status),
  CONSTRAINT fk_block_court FOREIGN KEY (court_id) REFERENCES court(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reservation_attendance (
  reservation_id BIGINT PRIMARY KEY,
  outcome VARCHAR(20) NOT NULL,
  recorded_by BIGINT NOT NULL,
  recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_attendance_reservation FOREIGN KEY (reservation_id) REFERENCES reservation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reservation_change (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  reservation_id BIGINT NOT NULL,
  request_key VARCHAR(64) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  before_snapshot JSON NOT NULL,
  after_snapshot JSON NOT NULL,
  balance_change_cents INT NOT NULL,
  points_change INT NOT NULL,
  changed_by BIGINT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_change_request (reservation_id, request_key),
  KEY idx_change_reservation (reservation_id, id),
  CONSTRAINT fk_change_reservation FOREIGN KEY (reservation_id) REFERENCES reservation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
