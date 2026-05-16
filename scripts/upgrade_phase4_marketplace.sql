USE badminton_platform;

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

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'member_account_transaction'
    AND COLUMN_NAME = 'shop_order_id'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE member_account_transaction ADD COLUMN shop_order_id BIGINT NULL AFTER reservation_id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @index_exists := (
  SELECT COUNT(*)
  FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'member_account_transaction'
    AND INDEX_NAME = 'idx_member_transaction_shop_order'
);
SET @sql := IF(
  @index_exists = 0,
  'ALTER TABLE member_account_transaction ADD KEY idx_member_transaction_shop_order (shop_order_id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @fk_exists := (
  SELECT COUNT(*)
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE()
    AND TABLE_NAME = 'member_account_transaction'
    AND CONSTRAINT_NAME = 'fk_member_transaction_shop_order'
);
SET @sql := IF(
  @fk_exists = 0,
  'ALTER TABLE member_account_transaction ADD CONSTRAINT fk_member_transaction_shop_order FOREIGN KEY (shop_order_id) REFERENCES shop_order(id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO shop_product (product_no, product_name, description, image_url, price_cents, stock, sold_count, status)
VALUES
  ('P001', '训练羽毛球', '耐打训练用球，适合日常练习。', '/courts/default-court.png', 6800, 30, 0, 1),
  ('P002', '吸汗手胶', '防滑吸汗手胶，到店领取。', '/courts/default-court.png', 1800, 80, 0, 1),
  ('P003', '场馆饮用水', '运动补水饮品，前台自提。', '/courts/default-court.png', 500, 120, 0, 1)
ON DUPLICATE KEY UPDATE
  product_name = VALUES(product_name),
  description = VALUES(description),
  image_url = VALUES(image_url),
  price_cents = VALUES(price_cents),
  stock = VALUES(stock),
  status = VALUES(status);
