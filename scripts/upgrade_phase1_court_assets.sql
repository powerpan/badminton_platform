USE badminton_platform;

SET @schema_name = DATABASE();

SET @court_asset_columns_missing = (
  SELECT IF(COUNT(*) < 4, 1, 0)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'court'
    AND COLUMN_NAME IN ('price_per_hour_cents', 'image_url', 'tags', 'capacity')
);

SET @reservation_money_columns_missing = (
  SELECT IF(COUNT(*) < 5, 1, 0)
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name
    AND TABLE_NAME = 'reservation'
    AND COLUMN_NAME IN (
      'price_per_hour_cents',
      'duration_minutes',
      'original_amount_cents',
      'discount_amount_cents',
      'payable_amount_cents'
    )
);

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE court ADD COLUMN price_per_hour_cents INT NOT NULL DEFAULT 12000 AFTER status',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'court' AND COLUMN_NAME = 'price_per_hour_cents'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE court ADD COLUMN image_url VARCHAR(500) NULL AFTER price_per_hour_cents',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'court' AND COLUMN_NAME = 'image_url'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE court ADD COLUMN tags VARCHAR(255) NULL AFTER image_url',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'court' AND COLUMN_NAME = 'tags'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE court ADD COLUMN capacity INT NOT NULL DEFAULT 6 AFTER tags',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'court' AND COLUMN_NAME = 'capacity'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN price_per_hour_cents INT NOT NULL DEFAULT 12000 AFTER remark',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'price_per_hour_cents'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN duration_minutes INT NOT NULL DEFAULT 60 AFTER price_per_hour_cents',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'duration_minutes'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN original_amount_cents INT NOT NULL DEFAULT 12000 AFTER duration_minutes',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'original_amount_cents'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN discount_amount_cents INT NOT NULL DEFAULT 0 AFTER original_amount_cents',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'discount_amount_cents'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE reservation ADD COLUMN payable_amount_cents INT NOT NULL DEFAULT 12000 AFTER discount_amount_cents',
    'DO 0'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @schema_name AND TABLE_NAME = 'reservation' AND COLUMN_NAME = 'payable_amount_cents'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE court
SET
  price_per_hour_cents = CASE court_no
    WHEN 'B01' THEN 10000
    ELSE 12000
  END,
  image_url = COALESCE(NULLIF(image_url, ''), '/courts/default-court.png'),
  tags = COALESCE(NULLIF(tags, ''), CASE court_no
    WHEN 'A01' THEN '空调开放,标准场地'
    WHEN 'A02' THEN '空调开放,休息区近'
    WHEN 'B01' THEN '训练区,轻量训练'
    ELSE '标准场地'
  END),
  capacity = CASE
    WHEN capacity IS NULL OR capacity <= 0 THEN 6
    WHEN court_no = 'B01' THEN 4
    ELSE capacity
  END
WHERE @court_asset_columns_missing = 1
   OR price_per_hour_cents <= 0
   OR image_url IS NULL
   OR image_url = ''
   OR tags IS NULL
   OR tags = ''
   OR capacity <= 0;

UPDATE reservation r
JOIN court c ON c.id = r.court_id
SET
  r.price_per_hour_cents = c.price_per_hour_cents,
  r.duration_minutes = TIMESTAMPDIFF(
    MINUTE,
    TIMESTAMP(r.reserve_date, r.start_time),
    TIMESTAMP(r.reserve_date, r.end_time)
  ),
  r.discount_amount_cents = 0,
  r.original_amount_cents = FLOOR(
    c.price_per_hour_cents * TIMESTAMPDIFF(
      MINUTE,
      TIMESTAMP(r.reserve_date, r.start_time),
      TIMESTAMP(r.reserve_date, r.end_time)
    ) / 60
  ),
  r.payable_amount_cents = FLOOR(
    c.price_per_hour_cents * TIMESTAMPDIFF(
      MINUTE,
      TIMESTAMP(r.reserve_date, r.start_time),
      TIMESTAMP(r.reserve_date, r.end_time)
    ) / 60
  )
WHERE @reservation_money_columns_missing = 1
   OR r.duration_minutes <= 0
   OR r.original_amount_cents <= 0
   OR r.payable_amount_cents <= 0;
