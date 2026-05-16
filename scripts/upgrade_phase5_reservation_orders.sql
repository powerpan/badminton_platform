USE badminton_platform;

SET @schema_name = DATABASE();

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

INSERT INTO config (config_key, config_value, description)
VALUES ('reservation_payment_timeout_minutes', '15', '预约待支付订单超时时间，单位分钟')
ON DUPLICATE KEY UPDATE
  description = VALUES(description);

