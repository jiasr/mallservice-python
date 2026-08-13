-- 用户协议与隐私政策表：后台可配置，小程序端展示
CREATE TABLE IF NOT EXISTS t_mall_agreement (
    id            INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    type          VARCHAR(32) NOT NULL DEFAULT 'agreement' COMMENT '类型: agreement=用户协议 privacy=隐私政策',
    title         VARCHAR(255) NOT NULL DEFAULT '' COMMENT '标题',
    content       LONGTEXT COMMENT '内容',
    version       VARCHAR(32) NOT NULL DEFAULT '1.0' COMMENT '版本号',
    status        TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1=启用 0=停用',
    create_time   DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户协议与隐私政策表';

-- 初始化默认数据（用户协议、隐私政策、关于我们各一条）
INSERT INTO t_mall_agreement (type, title, content, version, status) VALUES
('agreement', '用户协议', '欢迎使用本商城，请在使用前仔细阅读本用户协议。', '1.0', 1),
('privacy',   '隐私政策', '我们重视您的隐私保护，会依法收集、使用和保护您的个人信息。', '1.0', 1),
('about',     '关于我们', '关于我们的介绍内容', '1.0', 1)
ON DUPLICATE KEY UPDATE title = VALUES(title);
