DROP TABLE  regions;
CREATE TABLE regions (
    id VARCHAR(100) COMMENT '主键ID',
    code VARCHAR(20) NOT NULL  COMMENT '行政区划代码',
    name VARCHAR(100) NOT NULL COMMENT '名称',
    parent_code VARCHAR(20) COMMENT '父级代码',
    level VARCHAR(1) NOT NULL COMMENT '层级：1-省/直辖市，2-市，3-区/县',
    full_name VARCHAR(255) COMMENT '完整名称（如：北京市-北京市-东城区）',
    created_at TIMESTAMP DEFAULT NOW() COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='行政区划表';