-- 快递账号表增加中通开放平台(ZTO)渠道支持
-- 2026-09-04
-- 说明: provider 区分渠道(wechat=微信物流助手 / zto=中通开放平台);
--       中通渠道使用 app_key/app_secret/partner_code/env, 微信渠道使用 delivery_id/biz_id/password。

ALTER TABLE t_mall_delivery_account
    ADD COLUMN provider    VARCHAR(16)  NOT NULL DEFAULT 'wechat' COMMENT '渠道 wechat=微信物流助手 zto=中通开放平台' AFTER status,
    ADD COLUMN app_key     VARCHAR(128) NOT NULL DEFAULT ''        COMMENT '中通开放平台 appKey' AFTER provider,
    ADD COLUMN app_secret  VARCHAR(512) NOT NULL DEFAULT ''         COMMENT '中通开放平台 appSecret(AES-GCM 加密存储)' AFTER app_key,
    ADD COLUMN partner_code VARCHAR(64) NOT NULL DEFAULT ''         COMMENT '中通电子面单账号(如 D36_360320735712101)' AFTER app_secret,
    ADD COLUMN env         VARCHAR(16)  NOT NULL DEFAULT 'sandbox'  COMMENT '中通环境 sandbox/prod' AFTER partner_code;
