CREATE DATABASE IF NOT EXISTS badminton_platform
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE badminton_platform;

CREATE TABLE IF NOT EXISTS user (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  nickname VARCHAR(50) NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'user',
  contact VARCHAR(50) NULL,
  status TINYINT NOT NULL DEFAULT 1,
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_username (username),
  KEY idx_user_role (role),
  KEY idx_user_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS member_account (
  user_id BIGINT PRIMARY KEY,
  member_level VARCHAR(20) NOT NULL DEFAULT 'normal',
  balance_cents INT NOT NULL DEFAULT 0,
  points INT NOT NULL DEFAULT 0,
  expires_at DATE NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_member_level (member_level),
  KEY idx_member_expires_at (expires_at),
  CONSTRAINT fk_member_account_user FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS court (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  court_name VARCHAR(100) NOT NULL,
  court_no VARCHAR(50) NOT NULL,
  description VARCHAR(255) NULL,
  status TINYINT NOT NULL DEFAULT 1,
  price_per_hour_cents INT NOT NULL DEFAULT 12000,
  image_url VARCHAR(500) NULL,
  tags VARCHAR(255) NULL,
  capacity INT NOT NULL DEFAULT 6,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_court_no (court_no),
  KEY idx_court_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reservation (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  reservation_no VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  court_id BIGINT NOT NULL,
  reserve_date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  time_slot VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL,
  remark VARCHAR(255) NULL,
  price_per_hour_cents INT NOT NULL DEFAULT 12000,
  duration_minutes INT NOT NULL DEFAULT 60,
  original_amount_cents INT NOT NULL DEFAULT 12000,
  discount_amount_cents INT NOT NULL DEFAULT 0,
  payable_amount_cents INT NOT NULL DEFAULT 12000,
  member_level_snapshot VARCHAR(20) NOT NULL DEFAULT 'normal',
  discount_rate INT NOT NULL DEFAULT 100,
  points_awarded INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  canceled_at DATETIME NULL,
  UNIQUE KEY uk_reservation_no (reservation_no),
  KEY idx_reservation_user (user_id),
  KEY idx_reservation_court_date (court_id, reserve_date),
  KEY idx_reservation_status (status),
  KEY idx_reservation_slot (court_id, reserve_date, start_time, end_time),
  CONSTRAINT fk_reservation_user FOREIGN KEY (user_id) REFERENCES user(id),
  CONSTRAINT fk_reservation_court FOREIGN KEY (court_id) REFERENCES court(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS member_account_transaction (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  reservation_id BIGINT NULL,
  transaction_type VARCHAR(50) NOT NULL,
  balance_change_cents INT NOT NULL DEFAULT 0,
  points_change INT NOT NULL DEFAULT 0,
  balance_before_cents INT NOT NULL DEFAULT 0,
  balance_after_cents INT NOT NULL DEFAULT 0,
  points_before INT NOT NULL DEFAULT 0,
  points_after INT NOT NULL DEFAULT 0,
  reason VARCHAR(255) NULL,
  operator_id BIGINT NULL,
  operator_username VARCHAR(50) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_member_transaction_user (user_id),
  KEY idx_member_transaction_reservation (reservation_id),
  KEY idx_member_transaction_type (transaction_type),
  KEY idx_member_transaction_created_at (created_at),
  CONSTRAINT fk_member_transaction_user FOREIGN KEY (user_id) REFERENCES user(id),
  CONSTRAINT fk_member_transaction_reservation FOREIGN KEY (reservation_id) REFERENCES reservation(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS announcement (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  title VARCHAR(100) NOT NULL,
  content TEXT NOT NULL,
  status TINYINT NOT NULL DEFAULT 1,
  created_by BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_announcement_status (status),
  KEY idx_announcement_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS config (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  config_key VARCHAR(100) NOT NULL,
  config_value VARCHAR(255) NOT NULL,
  description VARCHAR(255) NULL,
  updated_by BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS operation_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NULL,
  username VARCHAR(50) NULL,
  role VARCHAR(20) NULL,
  module VARCHAR(50) NOT NULL,
  action VARCHAR(50) NOT NULL,
  target_type VARCHAR(50) NULL,
  target_id BIGINT NULL,
  detail TEXT NULL,
  ip VARCHAR(50) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_operation_log_user (user_id),
  KEY idx_operation_log_module (module),
  KEY idx_operation_log_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO config (config_key, config_value, description)
VALUES
  ('business_start_time', '09:00', '每日营业开始时间'),
  ('business_end_time', '21:00', '每日营业结束时间'),
  ('slot_interval_minutes', '60', '预约时间段间隔，单位分钟'),
  ('max_reservation_hours', '2', '单次最大预约小时数'),
  ('reservation_lock_ttl_seconds', '300', '预约锁超时时间，单位秒'),
  ('advance_reservation_days', '7', '可提前预约天数'),
  ('daily_reservation_limit', '3', '用户每日最大预约次数')
ON DUPLICATE KEY UPDATE
  config_value = VALUES(config_value),
  description = VALUES(description);

INSERT INTO court (court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity)
VALUES
  ('A01', '一号场', '靠近入口的标准羽毛球场地', 1, 12000, '/courts/default-court.png', '空调开放,标准场地', 6),
  ('A02', '二号场', '靠近休息区的标准羽毛球场地', 1, 12000, '/courts/default-court.png', '空调开放,休息区近', 6),
  ('B01', '三号场', '训练区场地', 1, 10000, '/courts/default-court.png', '训练区,轻量训练', 4)
ON DUPLICATE KEY UPDATE
  court_name = VALUES(court_name),
  description = VALUES(description),
  status = VALUES(status),
  price_per_hour_cents = VALUES(price_per_hour_cents),
  image_url = VALUES(image_url),
  tags = VALUES(tags),
  capacity = VALUES(capacity);

INSERT INTO user (username, password_hash, nickname, role, contact, status)
VALUES
  ('admin', '$2b$12$OeO2WdhDYO81lfFsEPMNle//zNjiWq5LuTAFbkK8RPLmv4wVTEAdu', '系统管理员', 'admin', 'admin', 1)
ON DUPLICATE KEY UPDATE
  password_hash = VALUES(password_hash),
  nickname = VALUES(nickname),
  role = VALUES(role),
  contact = VALUES(contact),
  status = VALUES(status);

INSERT INTO member_account (user_id, member_level, balance_cents, points, expires_at)
SELECT id, 'diamond', 200000, 0, '2026-12-31'
FROM user
WHERE username = 'admin'
ON DUPLICATE KEY UPDATE
  member_level = VALUES(member_level),
  balance_cents = VALUES(balance_cents),
  expires_at = VALUES(expires_at);
