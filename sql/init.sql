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

CREATE TABLE IF NOT EXISTS reservation_order (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no VARCHAR(64) NOT NULL,
  reservation_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  amount_cents INT NOT NULL DEFAULT 0,
  pay_method VARCHAR(20) NOT NULL DEFAULT 'balance',
  expires_at DATETIME NOT NULL,
  paid_at DATETIME NULL,
  canceled_at DATETIME NULL,
  cancel_reason VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reservation_order_no (order_no),
  UNIQUE KEY uk_reservation_order_reservation (reservation_id),
  KEY idx_reservation_order_user (user_id),
  KEY idx_reservation_order_status (status),
  KEY idx_reservation_order_expires (status, expires_at),
  CONSTRAINT fk_reservation_order_reservation FOREIGN KEY (reservation_id) REFERENCES reservation(id),
  CONSTRAINT fk_reservation_order_user FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_product (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_no VARCHAR(50) NOT NULL,
  product_name VARCHAR(100) NOT NULL,
  description TEXT NULL,
  image_url VARCHAR(500) NULL,
  price_cents INT NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  sold_count INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_shop_product_no (product_no),
  KEY idx_shop_product_status (status),
  KEY idx_shop_product_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_no VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL,
  total_amount_cents INT NOT NULL DEFAULT 0,
  pay_method VARCHAR(20) NOT NULL DEFAULT 'balance',
  paid_at DATETIME NULL,
  completed_at DATETIME NULL,
  canceled_at DATETIME NULL,
  cancel_reason VARCHAR(255) NULL,
  refund_requested_at DATETIME NULL,
  refund_request_reason VARCHAR(255) NULL,
  refund_reviewed_at DATETIME NULL,
  refund_reject_reason VARCHAR(255) NULL,
  remark VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_shop_order_no (order_no),
  KEY idx_shop_order_user (user_id),
  KEY idx_shop_order_status (status),
  KEY idx_shop_order_created_at (created_at),
  CONSTRAINT fk_shop_order_user FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS shop_order_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  order_id BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  product_no_snapshot VARCHAR(50) NOT NULL,
  product_name_snapshot VARCHAR(100) NOT NULL,
  image_url_snapshot VARCHAR(500) NULL,
  price_cents INT NOT NULL,
  quantity INT NOT NULL,
  subtotal_cents INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_shop_order_item_order (order_id),
  KEY idx_shop_order_item_product (product_id),
  CONSTRAINT fk_shop_order_item_order FOREIGN KEY (order_id) REFERENCES shop_order(id),
  CONSTRAINT fk_shop_order_item_product FOREIGN KEY (product_id) REFERENCES shop_product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS member_account_transaction (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  reservation_id BIGINT NULL,
  shop_order_id BIGINT NULL,
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
  KEY idx_member_transaction_shop_order (shop_order_id),
  KEY idx_member_transaction_type (transaction_type),
  KEY idx_member_transaction_created_at (created_at),
  CONSTRAINT fk_member_transaction_user FOREIGN KEY (user_id) REFERENCES user(id),
  CONSTRAINT fk_member_transaction_reservation FOREIGN KEY (reservation_id) REFERENCES reservation(id),
  CONSTRAINT fk_member_transaction_shop_order FOREIGN KEY (shop_order_id) REFERENCES shop_order(id)
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

CREATE TABLE IF NOT EXISTS notification (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  title VARCHAR(100) NOT NULL,
  content TEXT NOT NULL,
  category VARCHAR(50) NOT NULL DEFAULT 'system',
  source_type VARCHAR(50) NULL,
  source_id BIGINT NULL,
  is_read TINYINT NOT NULL DEFAULT 0,
  read_at DATETIME NULL,
  created_by BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_notification_user_read (user_id, is_read, created_at),
  KEY idx_notification_source (source_type, source_id),
  KEY idx_notification_created_at (created_at),
  CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES user(id),
  CONSTRAINT fk_notification_created_by FOREIGN KEY (created_by) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS club_event (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  title VARCHAR(100) NOT NULL,
  content TEXT NOT NULL,
  location VARCHAR(100) NOT NULL,
  start_at DATETIME NOT NULL,
  end_at DATETIME NOT NULL,
  registration_deadline DATETIME NOT NULL,
  capacity INT NOT NULL DEFAULT 20,
  status TINYINT NOT NULL DEFAULT 1,
  created_by BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_club_event_status (status),
  KEY idx_club_event_start_at (start_at),
  CONSTRAINT fk_club_event_created_by FOREIGN KEY (created_by) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS event_registration (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  event_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  canceled_at DATETIME NULL,
  UNIQUE KEY uk_event_registration_user (event_id, user_id),
  KEY idx_event_registration_event_status (event_id, status),
  KEY idx_event_registration_user (user_id),
  CONSTRAINT fk_event_registration_event FOREIGN KEY (event_id) REFERENCES club_event(id),
  CONSTRAINT fk_event_registration_user FOREIGN KEY (user_id) REFERENCES user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS community_post (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  content TEXT NOT NULL,
  status TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_community_post_user (user_id),
  KEY idx_community_post_status (status),
  KEY idx_community_post_created_at (created_at),
  CONSTRAINT fk_community_post_user FOREIGN KEY (user_id) REFERENCES user(id)
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
  ('reservation_payment_timeout_minutes', '15', '预约待支付订单超时时间，单位分钟'),
  ('advance_reservation_days', '7', '可提前预约天数'),
  ('daily_reservation_limit', '3', '用户每日最大预约次数')
ON DUPLICATE KEY UPDATE
  config_key = VALUES(config_key);

INSERT INTO court (court_no, court_name, description, status, price_per_hour_cents, image_url, tags, capacity)
VALUES
  ('A01', '一号场', '靠近入口的标准羽毛球场地', 1, 12000, '/courts/default-court.png', '空调开放,标准场地', 6),
  ('A02', '二号场', '靠近休息区的标准羽毛球场地', 1, 12000, '/courts/default-court.png', '空调开放,休息区近', 6),
  ('B01', '三号场', '训练区场地', 1, 10000, '/courts/default-court.png', '训练区,轻量训练', 4)
ON DUPLICATE KEY UPDATE
  court_no = VALUES(court_no);

INSERT INTO user (username, password_hash, nickname, role, contact, status)
VALUES
  ('admin', '$2b$12$TPjY/z1Ut.JJLpGI6hjaleO/bugGoC9C7ctepWJFjiFcVCkNz3GHi', '系统管理员', 'admin', 'admin', 1)
ON DUPLICATE KEY UPDATE
  username = VALUES(username);

INSERT INTO member_account (user_id, member_level, balance_cents, points, expires_at)
SELECT id, 'diamond', 200000, 0, '2026-12-31'
FROM user
WHERE username = 'admin'
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id);

INSERT INTO shop_product (product_no, product_name, description, image_url, price_cents, stock, sold_count, status)
VALUES
  ('P001', '训练羽毛球', '耐打训练用球，适合日常练习。', '/courts/default-court.png', 6800, 30, 0, 1),
  ('P002', '吸汗手胶', '防滑吸汗手胶，到店领取。', '/courts/default-court.png', 1800, 80, 0, 1),
  ('P003', '场馆饮用水', '运动补水饮品，前台自提。', '/courts/default-court.png', 500, 120, 0, 1)
ON DUPLICATE KEY UPDATE
  product_no = VALUES(product_no);
