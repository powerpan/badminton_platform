USE badminton_platform;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shop_order'
    AND COLUMN_NAME = 'refund_requested_at'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE shop_order ADD COLUMN refund_requested_at DATETIME NULL AFTER cancel_reason',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shop_order'
    AND COLUMN_NAME = 'refund_request_reason'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE shop_order ADD COLUMN refund_request_reason VARCHAR(255) NULL AFTER refund_requested_at',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shop_order'
    AND COLUMN_NAME = 'refund_reviewed_at'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE shop_order ADD COLUMN refund_reviewed_at DATETIME NULL AFTER refund_request_reason',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @column_exists := (
  SELECT COUNT(*)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'shop_order'
    AND COLUMN_NAME = 'refund_reject_reason'
);
SET @sql := IF(
  @column_exists = 0,
  'ALTER TABLE shop_order ADD COLUMN refund_reject_reason VARCHAR(255) NULL AFTER refund_reviewed_at',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
