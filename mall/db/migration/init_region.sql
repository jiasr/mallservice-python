CREATE TABLE regions (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    code VARCHAR(20) NOT NULL UNIQUE COMMENT '行政区划代码',
    name VARCHAR(100) NOT NULL COMMENT '名称',
    parent_code VARCHAR(20) COMMENT '父级代码',
    level TINYINT NOT NULL COMMENT '层级：1-省/直辖市，2-市，3-区/县',
    full_name VARCHAR(255) COMMENT '完整名称（如：北京市-北京市-东城区）',
    created_at TIMESTAMP DEFAULT NOW() COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',

    INDEX idx_parent_code (parent_code),
    INDEX idx_level (level),
    INDEX idx_code (code),
    FOREIGN KEY (parent_code) REFERENCES regions(code) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行政区划表';