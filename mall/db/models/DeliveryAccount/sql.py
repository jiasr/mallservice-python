"""快递公司账号绑定数据访问层

对应模型 mall.db.models.DeliveryAccount.model.DeliveryAccount（t_mall_delivery_account）。
支持多渠道:
- wechat: delivery_id + biz_id + password(加密)
- zto: app_key + app_secret(加密) + partner_code + env

密码/密钥入库做 AES-GCM 加密存储（规范要求）；中通下单需回读 app_secret，故提供 _decrypt_password 解密。
"""
import uuid
import hashlib
import os
import base64
import logging

from mall.db.engines.mysql import get_session
from mall.db.models.DeliveryAccount.model import DeliveryAccount
from mall.common.common import Fail

LOG = logging.getLogger(__name__)

_SECRET_KEY = None


def _get_secret_key():
    """派生加密密钥：优先使用系统配置，缺失时降级为开发期固定密钥。"""
    global _SECRET_KEY
    if _SECRET_KEY is None:
        key_src = "mall-dev-secret-key"
        try:
            from mall.service.setting_service import get_all_settings
            s = get_all_settings() or {}
            key_src = s.get("express_aes_key") or s.get("app_secret") or key_src
        except Exception:
            pass
        _SECRET_KEY = hashlib.sha256(key_src.encode("utf-8")).digest()
    return _SECRET_KEY


def _encrypt_password(plain):
    """密码/密钥加密存储（AES-GCM），失败降级明文并告警。"""
    if not plain:
        return ""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _get_secret_key()
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plain.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("utf-8")
    except Exception as e:
        LOG.warning("密码加密失败，降级为明文存储: %s", e)
        return plain


def _decrypt_password(cipher):
    """解密密码/密钥（AES-GCM），失败返回空串。"""
    if not cipher:
        return ""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _get_secret_key()
        raw = base64.b64decode(cipher)
        nonce, ct = raw[:12], raw[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception as e:
        LOG.warning("密码解密失败: %s", e)
        return ""


class DeliveryAccountDao:

    @classmethod
    def list(cls, page_num=1, page_size=20, status=None, provider=None):
        """账号列表（分页），provider 可选过滤渠道"""
        session = get_session()
        with session.begin():
            q = session.query(DeliveryAccount)
            if status is not None:
                q = q.filter(DeliveryAccount.status == status)
            if provider is not None:
                q = q.filter(DeliveryAccount.provider == provider)
            total = q.count()
            rows = (
                q.order_by(DeliveryAccount.create_time.desc())
                .limit(page_size)
                .offset((page_num - 1) * page_size)
                .all()
            )
            return {
                "total": total,
                "list": [r.to_dict() for r in rows],
            }

    @classmethod
    def get_by_id(cls, account_id):
        session = get_session()
        with session.begin():
            acc = session.query(DeliveryAccount).filter(DeliveryAccount.id == account_id).first()
            if not acc:
                raise Fail("DELIVERY_ACCOUNT_NOT_FOUND", {}, "快递账号不存在")
            return acc.to_dict()

    @classmethod
    def create(cls, data):
        """新增绑定账号（按 provider 区分渠道存储）"""
        provider = data.get("provider", "wechat")
        is_zto = provider == "zto"
        session = get_session()
        with session.begin():
            acc = DeliveryAccount(
                id=uuid.uuid4().hex,
                provider=provider,
                delivery_id=data.get("deliveryId", ""),
                biz_id=data.get("bizId", ""),
                account_name=(
                    data.get("accountName")
                    or (data.get("partnerCode", "") if is_zto else data.get("deliveryId", ""))
                ),
                password=_encrypt_password(data.get("password", "")) if not is_zto else "",
                app_key=data.get("appKey", "") if is_zto else "",
                app_secret=_encrypt_password(data.get("appSecret", "")) if is_zto else "",
                partner_code=data.get("partnerCode", "") if is_zto else "",
                customer_id=data.get("customerId", "") if is_zto else "",
                partner_key=_encrypt_password(data.get("partnerKey", "")) if is_zto else "",
                partner_type=data.get("partnerType", "1") if is_zto else "",
                env=data.get("env", "sandbox") if is_zto else "",
                status=1,
            )
            session.add(acc)
            session.flush()
            return {"id": acc.id}

    @classmethod
    def update(cls, account_id, data):
        """更新账号（名称/状态/渠道字段）"""
        session = get_session()
        with session.begin():
            acc = session.query(DeliveryAccount).filter(DeliveryAccount.id == account_id).first()
            if not acc:
                raise Fail("DELIVERY_ACCOUNT_NOT_FOUND", {}, "快递账号不存在")
            if "provider" in data:
                acc.provider = data["provider"]
            if "accountName" in data:
                acc.account_name = data["accountName"]
            if "status" in data:
                acc.status = int(data["status"])
            if "deliveryId" in data:
                acc.delivery_id = data["deliveryId"]
            if "bizId" in data:
                acc.biz_id = data["bizId"]
            if data.get("password"):
                acc.password = _encrypt_password(data["password"])
            if "appKey" in data:
                acc.app_key = data["appKey"]
            if data.get("appSecret"):
                acc.app_secret = _encrypt_password(data["appSecret"])
            if "partnerCode" in data:
                acc.partner_code = data["partnerCode"]
            if "customerId" in data:
                acc.customer_id = data["customerId"]
            if data.get("partnerKey"):
                acc.partner_key = _encrypt_password(data["partnerKey"])
            if "partnerType" in data:
                acc.partner_type = data["partnerType"]
            if "env" in data:
                acc.env = data["env"]
            return {"id": acc.id}

    @classmethod
    def delete(cls, account_id):
        session = get_session()
        with session.begin():
            acc = session.query(DeliveryAccount).filter(DeliveryAccount.id == account_id).first()
            if not acc:
                raise Fail("DELIVERY_ACCOUNT_NOT_FOUND", {}, "快递账号不存在")
            session.delete(acc)
            return {"success": True}

    @classmethod
    def upsert_from_wechat(cls, accounts):
        """从微信同步：按 (delivery_id, biz_id) 唯一键 upsert"""
        session = get_session()
        with session.begin():
            added = 0
            for a in (accounts or []):
                did = a.get("delivery_id", "")
                bid = a.get("biz_id", "")
                if not did or not bid:
                    continue
                existing = (
                    session.query(DeliveryAccount)
                    .filter(
                        DeliveryAccount.delivery_id == did,
                        DeliveryAccount.biz_id == bid,
                    )
                    .first()
                )
                if existing:
                    existing.account_name = (
                        a.get("remark") or a.get("account_name") or existing.account_name
                    )
                    existing.status = 1
                else:
                    session.add(
                        DeliveryAccount(
                            id=uuid.uuid4().hex,
                            provider="wechat",
                            delivery_id=did,
                            biz_id=bid,
                            account_name=a.get("remark") or a.get("account_name") or did,
                            password="",
                            status=1,
                        )
                    )
                    added += 1
            total = session.query(DeliveryAccount).count()
            return {"synced": len(accounts or []), "added": added, "total": total}
