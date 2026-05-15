USE badminton_platform;

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
