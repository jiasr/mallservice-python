-- ============================================
-- 商城系统数据库初始化脚本
-- 使用方法: mysql -u root -p < init.sql
-- ============================================

CREATE DATABASE IF NOT EXISTS mall DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE MALL;

-- ============================================ 商品模块 ============================================

CREATE TABLE IF NOT EXISTS t_mall_goods_spu (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    spu_id          VARCHAR(255) NOT NULL DEFAULT'' COMMENT 'SPU唯一标识',
    title           VARCHAR(500) NOT NULL          COMMENT '商品标题',
    category_id     VARCHAR(255)                   COMMENT '分类ID',
    is_put_on_sale  INT DEFAULT 1                  COMMENT '是否上架 1是0否',
    is_available    INT DEFAULT 1                  COMMENT '是否可用 1是0否',
    images          TEXT                           COMMENT '商品图片/视频(JSON数组,第一张为主图)',
    `desc`          TEXT                           COMMENT '商品详情(富文本HTML)',
    sold_num        INT DEFAULT 0                  COMMENT '已售数量',
    is_sold_out     TINYINT(1) DEFAULT 0           COMMENT '是否售罄',
    tags            VARCHAR(500)                   COMMENT '标签(JSON数组)',
    store_id        VARCHAR(64) DEFAULT '1000'     COMMENT '店铺ID',
    create_time     DATETIME DEFAULT NOW()         COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
    min_sale_price  INT DEFAULT 0                  COMMENT '最低售价(分)',
    max_sale_price  INT DEFAULT 0                  COMMENT '最高售价(分)',
    min_line_price  INT DEFAULT 0                  COMMENT '最低划线价(分)',
    max_line_price  INT DEFAULT 0                  COMMENT '最高划线价(分)',
    stock_quantity  INT DEFAULT 0                  COMMENT '总库存'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品SPU表';

CREATE TABLE IF NOT EXISTS t_mall_goods_sku (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    sku_id          VARCHAR(255) NOT NULL DEFAULT'' COMMENT 'SKU唯一标识',
    spu_id          VARCHAR(255)                  COMMENT '关联SPU',
    sku_image       VARCHAR(500)                  COMMENT 'SKU图片',
    price           INT DEFAULT 0                 COMMENT '销售价格(分)',
    line_price      INT DEFAULT 0                 COMMENT '划线价格(分)',
    stock_quantity  INT DEFAULT 0                 COMMENT '库存数量',
    sold_quantity   INT DEFAULT 0                 COMMENT '已售数量',
    spec_info       TEXT                          COMMENT '规格信息(JSON数组)',
    weight_value    FLOAT                         COMMENT '重量',
    weight_unit     VARCHAR(10) DEFAULT 'KG'      COMMENT '重量单位',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
    FOREIGN KEY (spu_id) REFERENCES t_mall_goods_spu(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品SKU表';

CREATE TABLE IF NOT EXISTS t_mall_goods_spec (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    spec_id         VARCHAR(255) NOT NULL DEFAULT'' COMMENT '规格唯一标识',
    spu_id          VARCHAR(255)                  COMMENT '关联SPU',
    title           VARCHAR(100) NOT NULL          COMMENT '规格名称(如颜色、尺码)',
    spec_values     TEXT                          COMMENT '规格值列表(JSON数组)',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品规格定义表';

-- ============================================ 分类模块 ============================================

CREATE TABLE IF NOT EXISTS t_mall_goods_catalog (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    name            VARCHAR(255) NOT NULL          COMMENT '分类名称',
    parentid        VARCHAR(255) DEFAULT '0'       COMMENT '父分类ID',
    `level`         INT DEFAULT 0                 COMMENT '层级:1一级 2二级 3三级',
    thumbnail       VARCHAR(500)                  COMMENT '分类缩略图',
    sort_order      INT DEFAULT 0                 COMMENT '排序',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品分类表';

-- ============================================ 用户模块 ============================================

CREATE TABLE IF NOT EXISTS t_mall_user (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    name            VARCHAR(255)                  COMMENT '用户名',
    wx_openid       VARCHAR(255)                  COMMENT '微信OpenID',
    wx_unionid      VARCHAR(255)                  COMMENT '微信UnionID',
    wx_session_key  VARCHAR(255)                  COMMENT '微信SessionKey',
    INDEX idx_openid (wx_openid),
    INDEX idx_unionid (wx_unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

CREATE TABLE IF NOT EXISTS t_mall_user_address (
    id              VARCHAR(255) PRIMARY KEY      COMMENT '主键ID',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '修改时间',
    userid          VARCHAR(255)                  COMMENT '用户ID',
    name            VARCHAR(255)                  COMMENT '收货人姓名',
    mobile          VARCHAR(20)                   COMMENT '收货人手机号',
    province        VARCHAR(30)                   COMMENT '省',
    provincecode    VARCHAR(30)                   COMMENT '省编码',
    city            VARCHAR(30)                   COMMENT '市',
    citycode        VARCHAR(30)                   COMMENT '市编码',
    district        VARCHAR(30)                   COMMENT '区县',
    districtcode    VARCHAR(30)                   COMMENT '区县编码',
    detail          VARCHAR(255)                  COMMENT '详细地址',
    is_defalut      INT DEFAULT 1                 COMMENT '是否默认 1是0否',
    addressTag      VARCHAR(30)                   COMMENT '地址标签'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户地址表';

-- ============================================ 管理员模块 ============================================

CREATE TABLE IF NOT EXISTS t_mall_admin_role (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name            VARCHAR(64) UNIQUE NOT NULL    COMMENT '角色名称',
    description     VARCHAR(255) DEFAULT ''        COMMENT '角色描述',
    status          INT DEFAULT 1                 COMMENT '状态 1启用0禁用',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员角色表';

CREATE TABLE IF NOT EXISTS t_mall_admin_menu (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    name            VARCHAR(64) NOT NULL           COMMENT '菜单名称',
    frontpath       VARCHAR(255) DEFAULT ''        COMMENT '前端路由路径',
    icon            VARCHAR(64) DEFAULT ''         COMMENT '图标名称',
    parent_id       INT DEFAULT 0                 COMMENT '父菜单ID,0为顶级',
    sort_order      INT DEFAULT 0                 COMMENT '排序号',
    permission      VARCHAR(128) DEFAULT ''        COMMENT '权限标识如goods:add',
    visible         INT DEFAULT 1                 COMMENT '是否可见 1是0否',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员菜单/权限表';

CREATE TABLE IF NOT EXISTS t_mall_admin_role_menu (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    role_id         INT NOT NULL                   COMMENT '角色ID',
    menu_id         INT NOT NULL                   COMMENT '菜单ID',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    FOREIGN KEY (role_id) REFERENCES t_mall_admin_role(id),
    FOREIGN KEY (menu_id) REFERENCES t_mall_admin_menu(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色-菜单关联表';

CREATE TABLE IF NOT EXISTS t_mall_admin_user (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    username        VARCHAR(64) UNIQUE NOT NULL    COMMENT '用户名',
    password_hash   VARCHAR(128) NOT NULL          COMMENT '密码哈希',
    avatar          VARCHAR(500) DEFAULT ''        COMMENT '头像URL',
    role_id         INT                           COMMENT '角色ID',
    status          INT DEFAULT 1                 COMMENT '状态 1启用0禁用',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
    FOREIGN KEY (role_id) REFERENCES t_mall_admin_role(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员用户表';

-- ============================================ 系统配置模块 ============================================

CREATE TABLE IF NOT EXISTS t_mall_system_config (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    config_key      VARCHAR(128) UNIQUE NOT NULL   COMMENT '配置键名',
    config_value    TEXT DEFAULT ''                COMMENT '配置值',
    description     VARCHAR(255) DEFAULT ''        COMMENT '配置说明',
    config_group    VARCHAR(64) DEFAULT 'general'  COMMENT '配置分组',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';

CREATE TABLE IF NOT EXISTS t_mall_storage_config (
    id              INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    endpoint        VARCHAR(512) DEFAULT 'http://82.156.225.136:9000' COMMENT 'S3端点地址',
    access_key      VARCHAR(256) DEFAULT 'admin'   COMMENT 'AccessKey ID',
    secret_key      VARCHAR(256) DEFAULT 'password123' COMMENT 'AccessKey Secret',
    bucket_name     VARCHAR(128) DEFAULT 'mall-images1' COMMENT 'Bucket名称',
    region          VARCHAR(64) DEFAULT 'us-east-1' COMMENT '地域',
    public_endpoint VARCHAR(512) DEFAULT 'http://82.156.225.136:9000' COMMENT '公网访问地址',
    create_time     DATETIME DEFAULT NOW()        COMMENT '创建时间',
    update_time     DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='对象存储配置表';

-- ============================================ 默认数据 ============================================

-- 默认超级管理员角色
INSERT INTO t_mall_admin_role (id,name,description) VALUES (1,'超级管理员','拥有所有权限') ON DUPLICATE KEY UPDATE name=name;

-- 默认菜单
INSERT INTO t_mall_admin_menu (id,name,frontpath,icon,parent_id,sort_order,permission) VALUES
(1, '仪表盘',   '/dashboard',   'Monitor',  0,1,''),
(2, '商品管理',  '',            'Goods',    0,2,''),
(3, '商品列表',  '/goods/list',  '',         2,1,'goods:list'),
(4, '添加商品',  '/goods/add',   '',         2,2,'goods:add'),
(5, '分类管理',  '/category/list','',        2,3,'category:list'),
(6, '系统设置',  '',            'Setting',  0,3,''),
(7, '基本设置',  '/setting/basic','',        6,1,'setting:basic'),
(8, '存储配置',  '/setting/storage','',      6,2,'setting:storage'),
(9, '用户管理',  '/user/list',  'User',      0,4,'user:list')
ON DUPLICATE KEY UPDATE name=name;

-- 管理员默认菜单权限
INSERT INTO t_mall_admin_role_menu (role_id,menu_id) VALUES
(1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(1,9)
ON DUPLICATE KEY UPDATE role_id=role_id;

-- 默认系统配置
INSERT INTO t_mall_system_config (config_key,config_value,description,config_group) VALUES
('site_name',       '商城系统',     '网站名称',       'general'),
('site_logo',       '',            '网站Logo URL',   'general'),
('site_icp',        '',            'ICP备案号',      'general'),
('site_keywords',   '',            'SEO关键词',      'general'),
('site_description','',            'SEO描述',        'general')
ON DUPLICATE KEY UPDATE config_value=config_value;

-- 默认存储配置
INSERT INTO t_mall_storage_config (id,endpoint,access_key,secret_key,bucket_name,region,public_endpoint) VALUES
(1,'http://82.156.225.136:9000','admin','password123','mall-images1','us-east-1','http://82.156.225.136:9000')
ON DUPLICATE KEY UPDATE endpoint=endpoint;
