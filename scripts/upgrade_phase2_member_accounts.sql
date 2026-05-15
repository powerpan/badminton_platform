USE badminton_platform;

SET @schema_name = DATABASE();

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

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN member_level_snapshot VARCHAR(20) NOT NULL DEFAULT ''normal'' AFTER payable_amount_cents',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'member_level_snapshot'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN discount_rate INT NOT NULL DEFAULT 100 AFTER member_level_snapshot',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'discount_rate'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN points_awarded INT NOT NULL DEFAULT 0 AFTER discount_rate',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'points_awarded'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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

INSERT INTO member_account (user_id, member_level, balance_cents, points, expires_at)
SELECT
  u.id,
  CASE WHEN u.username = 'admin' THEN 'diamond' ELSE 'normal' END,
  CASE WHEN u.username = 'admin' THEN 200000 ELSE 0 END,
  0,
  CASE WHEN u.username = 'admin' THEN '2026-12-31' ELSE NULL END
FROM user u
LEFT JOIN member_account ma ON ma.user_id = u.id
WHERE ma.user_id IS NULL;

UPDATE reservation
SET
  member_level_snapshot = COALESCE(NULLIF(member_level_snapshot, ''), 'normal'),
  discount_rate = CASE WHEN discount_rate IS NULL OR discount_rate <= 0 THEN 100 ELSE discount_rate END,
  points_awarded = CASE WHEN points_awarded IS NULL OR points_awarded < 0 THEN 0 ELSE points_awarded END;
