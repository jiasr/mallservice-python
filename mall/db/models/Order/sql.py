"""订单数据访问层"""
import json
import math
import random
from datetime import datetime
from sqlalchemy import func
from mall.db.engines.mysql import get_session
from mall.db.models.Order.model import Order, OrderItem
from mall.db.models.Goods.model import GoodsSpu, GoodsSku
from mall.db.models.Cart.model import Cart
from mall.db.models.User.model import UserAddress
from mall.db.models.Stock.sql import InvGoodsDao
from mall.db.models.Freight.sql import FreightCalculator
from mall.db.engines.s3 import get_image_display_url
from mall.common.common import Fail


def _img_url(path):
    if not path:
        return ''
    imgs = json.loads(path) if path else []
    if isinstance(imgs, list) and len(imgs) > 0:
        return get_image_display_url(imgs[0])
    return get_image_display_url(path)


def _generate_order_id(session):
    """生成全局唯一订单号: {年月日时分秒毫秒}{6位随机数}

    不依赖数据库当天流水号，避免清库/重置后订单号从1开始，
    与微信侧历史支付记录冲突（ORDERPAID: 该订单已支付）。
    毫秒级时间戳 + 6位随机数，同一毫秒内可容纳100万个订单号，
    保证每次生成全局唯一，满足高并发下单场景。
    """
    now = datetime.now()
    ts = now.strftime('%Y%m%d%H%M%S') + '{:03d}'.format(now.microsecond // 1000)
    return '{}{:06d}'.format(ts, random.randint(0, 999999))


class OrderDao:

    @classmethod
    def list(cls, user_id, page_num=1, page_size=10, order_status=None):
        """获取订单列表（不含回收站已删除订单）"""
        session = get_session()
        with session.begin():
            q = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0)
            if order_status is not None and int(order_status) >= 0:
                q = q.filter(Order.order_status == int(order_status))
            total = q.count()
            q = q.order_by(Order.create_time.desc()).limit(page_size).offset((page_num - 1) * page_size)
            orders = q.all()
            return {'data': {
                'total': total,
                'orders': [cls._format_order_list(o, session) for o in orders],
            }}

    @classmethod
    def count_by_status(cls, user_id):
        """获取各状态订单数量"""
        session = get_session()
        with session.begin():
            total = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0).count()
            pending_pay = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0, Order.order_status == 0).count()
            pending_deliver = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0, Order.order_status == 1).count()
            pending_receipt = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0, Order.order_status == 2).count()
            complete = session.query(Order).filter(Order.user_id == user_id, Order.deleted == 0, Order.order_status == 3).count()
            return {'data': [
                {'orderNum': pending_pay},
                {'orderNum': pending_deliver},
                {'orderNum': pending_receipt},
                {'orderNum': complete},
            ]}

    @classmethod
    def _format_order_list(cls, order, session):
        """格式化订单为前端需要的格式"""
        items = session.query(OrderItem).filter(OrderItem.order_id == order.order_id).all()
        return {
            'id': order.id,
            'orderId': order.order_id,
            'orderNo': order.order_id,
            'parentOrderNo': '',
            'storeId': '1000',
            'storeName': '',
            'orderStatus': order.order_status,
            'orderStatusName': cls._status_name(order.order_status),
            'paymentAmount': order.pay_amount,
            'totalAmount': order.total_amount,
            'freightFee': order.freight_amount,
            'deliveryType': order.delivery_type,
            'logisticsVO': {'logisticsNo': ''},
            'createTime': cls._fmt_dt(order.create_time),
            'paidAt': cls._fmt_dt(order.paid_at),
            'shippedAt': cls._fmt_dt(order.shipped_at),
            'completedAt': cls._fmt_dt(order.completed_at),
            'canceledAt': cls._fmt_dt(order.canceled_at),
            'orderItemVOs': [{
                'id': item.id,
                'goodsPictureUrl': get_image_display_url(item.thumb) if item.thumb else '',
                'goodsName': item.title,
                'goodsCount': item.quantity,
                'realPrice': item.price,
                'specInfo': [{'specValue': item.spec_label}],
            } for item in items],
        }

    @classmethod
    def admin_list(cls, page_num=1, page_size=10, order_status=None, order_no='', consignee='', phone='', pay_status=None):
        """管理员订单列表（查所有用户，不含回收站已删除订单）"""
        session = get_session()
        with session.begin():
            q = session.query(Order).filter(Order.deleted == 0)
            if order_status is not None and int(order_status) >= 0:
                q = q.filter(Order.order_status == int(order_status))
            # 支付/退款状态筛选，支持逗号分隔多值: 1=已支付 2=已退款
            if pay_status:
                statuses = [int(s) for s in str(pay_status).split(',') if s.strip().isdigit()]
                if statuses:
                    q = q.filter(Order.pay_status.in_(statuses))
            if order_no:
                q = q.filter(Order.order_id.like('%' + order_no + '%'))
            if consignee:
                q = q.filter(Order.consignee_name.like('%' + consignee + '%'))
            if phone:
                q = q.filter(Order.consignee_mobile.like('%' + phone + '%'))
            total = q.count()
            q = q.order_by(Order.create_time.desc()).limit(page_size).offset((page_num - 1) * page_size)
            orders = q.all()
            return {'data': {
                'total': total,
                'list': [cls._format_admin_order(o, session) for o in orders],
            }}

    @classmethod
    def admin_process(cls, order_no, data):
        """管理员处理订单（发货）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_no).first()
            if not order:
                return {'success': False, 'message': '订单不存在'}
            if 'shippingCompany' in data:
                order.order_status = 2
                order.shipped_at = datetime.now()
                order.shipping_company = data.get('shippingCompany', '')
                order.shipping_no = data.get('shippingNo', '')
            elif data.get('action') == 'complete':
                order.order_status = 3
                order.completed_at = datetime.now()
            elif int(data.get('status', 0)) == -1 or data.get('action') == 'cancel':
                # 后台取消订单：仅待付款可取消（已付款请走退款）
                if order.order_status != 0:
                    return {'success': False, 'message': '当前订单状态不可取消'}
                order.order_status = 4
                order.canceled_at = datetime.now()
            return {'success': True}

    @classmethod
    def admin_detail(cls, order_no):
        """管理员订单详情"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_no).first()
            if not order:
                return {'success': False, 'message': '订单不存在'}
            return {'data': cls._format_admin_order(order, session)}

    @classmethod
    def _format_admin_order(cls, order, session):
        items = session.query(OrderItem).filter(OrderItem.order_id == order.order_id).all()
        goods_amount = sum((it.price or 0) * (it.quantity or 0) for it in items)
        # 按 SKU 批量查询条码（订单明细表不存条码，下单后 SKU 可能变化，以当前 SKU 条码为准）
        sku_ids = [it.sku_id for it in items]
        barcode_map = {}
        if sku_ids:
            rows = session.query(GoodsSku.sku_id, GoodsSku.barcode).filter(
                GoodsSku.sku_id.in_(sku_ids)
            ).all()
            barcode_map = {r[0]: (r[1] or '') for r in rows}
        return {
            'orderNo': order.order_id,
            'consignee': order.consignee_name,
            'phone': order.consignee_mobile,
            'address': order.consignee_address,
            'status': order.order_status,
            'payStatus': order.pay_status,
            'totalAmount': order.total_amount,
            'payAmount': order.pay_amount,
            'freightAmount': order.freight_amount,
            'deliveryType': order.delivery_type,
            'remark': order.remark,
            'createTime': cls._fmt_dt(order.create_time),
            'paidAt': cls._fmt_dt(order.paid_at),
            'payTime': cls._fmt_dt(order.paid_at),
            'shippedAt': cls._fmt_dt(order.shipped_at),
            'completedAt': cls._fmt_dt(order.completed_at),
            'canceledAt': cls._fmt_dt(order.canceled_at),
            'deletedAt': cls._fmt_dt(order.deleted_at),
            'paymentMethod': order.payment_method or '',
            'goodsAmount': goods_amount,
            'discountAmount': goods_amount + (order.freight_amount or 0) - (order.pay_amount or 0),
            'shippingCompany': order.shipping_company or '',
            'shippingNo': order.shipping_no or '',
            'orderItemList': [{
                'title': it.title,
                'thumb': get_image_display_url(it.thumb) if it.thumb else '',
                'specInfo': [{'specValue': it.spec_label}],
                'barcode': barcode_map.get(it.sku_id, ''),
                'price': it.price,
                'quantity': it.quantity,
                'subtotal': (it.price or 0) * (it.quantity or 0),
            } for it in items],
        }

    @classmethod
    def admin_print(cls, order_no):
        """获取订单小票打印数据（订单 + 店铺信息）"""
        from mall.service.setting_service import get_all_settings
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_no).first()
            if not order:
                return {'success': False, 'message': '订单不存在'}
            settings = get_all_settings()
            shop = {
                'name': settings.get('site_name', ''),
                'phone': settings.get('service_phone', ''),
                'email': settings.get('service_email', ''),
            }
            return {'success': True, 'data': {
                'order': cls._format_admin_order(order, session),
                'shop': shop,
            }}

    @staticmethod
    def _status_name(status):
        names = {0: '待付款', 1: '待发货', 2: '待收货', 3: '已完成', 4: '已取消'}
        return names.get(status, '未知')

    @staticmethod
    def _fmt_dt(dt):
        """格式化 DateTime 为 'YYYY-MM-DD HH:mm:ss'，空值返回 ''"""
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else ''

    @classmethod
    def preview(cls, user_id, items, province_code='', delivery_type=0):
        """订单预览（只算金额，不写DB）"""
        session = get_session()
        result_items = []
        total = 0
        with session.begin():
            for it in items:
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == it['skuId']).first()
                spu = session.query(GoodsSpu).filter(GoodsSpu.spu_id == it['spuId']).first()
                if not sku or not spu:
                    raise Fail("SKU_NOT_FOUND", {}, "商品不存在")
                # 实时读取进销存真实库存判断售罄
                inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
                real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
                if real_stock <= 0:
                    raise Fail("STOCK_EMPTY", {}, "{} 已售罄".format(spu.title))
                qty = int(it.get('quantity', 1))
                price = sku.price
                spec_info = json.loads(sku.spec_info) if sku.spec_info else []
                spec_label = '/'.join([s.get('specValues', s.get('specValue', '')) for s in spec_info])
                imgs_raw = json.loads(spu.images) if spu.images else []
                thumb = get_image_display_url(imgs_raw[0]) if imgs_raw else ''
                total += price * qty
                result_items.append({
                    'spuId': spu.spu_id,
                    'skuId': sku.sku_id,
                    'title': spu.title,
                    'thumb': thumb,
                    'specLabel': spec_label,
                    'price': price,
                    'quantity': qty,
                    'subtotal': price * qty,
                })

        # 计算运费
        freight_items = [{'spu_id': it['spuId'], 'quantity': it['quantity']} for it in items]
        freight_amount = FreightCalculator.calc(freight_items, province_code, total)

        return {
            'totalAmount': total,
            'discountAmount': 0,
            'freightAmount': freight_amount,
            'payAmount': total + freight_amount,
            'deliveryType': delivery_type,
            'items': result_items,
        }

    @classmethod
    def create(cls, user_id, data):
        """创建订单（库存扣减使用悲观锁）"""
        items = data.get('items', [])
        consignee = data.get('consignee', {})
        remark = data.get('remark', '')
        delivery_type = int(data.get('deliveryType', 0))
        pickup_store_id = int(data.get('pickupStoreId', 0))
        pickup_store_name = data.get('pickupStoreName', '')
        local_delivery_time = data.get('localDeliveryTime', '')
        province_code = consignee.get('provinceCode', '')

        session = get_session()
        with session.begin():
            order_id = _generate_order_id(session)
            order_items = []
            total_amount = 0

            for it in items:
                sku = session.query(GoodsSku).filter(
                    GoodsSku.sku_id == it['skuId']
                ).with_for_update().first()

                spu = session.query(GoodsSpu).filter(
                    GoodsSpu.spu_id == it['spuId']
                ).first()

                if not sku or not spu:
                    raise Fail("SKU_NOT_FOUND", {}, "商品不存在")

                qty = int(it.get('quantity', 1))

                # 实时读取进销存真实库存作为库存校验口径
                inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
                real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
                if real_stock < qty:
                    raise Fail("STOCK_NOT_ENOUGH", {}, "{} 库存不足".format(spu.title))

                # 扣减商城SKU库存（兼容层，权威库存以进销存为准）
                sku.stock_quantity -= qty

                # 实时联动扣减进销存库存（同一事务）：SKU 无条码或进销存无匹配商品时降级跳过
                inv_goods, inv_err = InvGoodsDao.adjust_by_barcode(
                    session, sku.barcode, -qty, order_id,
                    remark='销售出库: 订单 {}'.format(order_id),
                )
                if inv_err:
                    # 进销存库存不足：回滚已扣的SKU库存并报错
                    sku.stock_quantity += qty
                    raise Fail("STOCK_NOT_ENOUGH", {}, "{} 库存不足".format(spu.title))

                price = sku.price
                subtotal = price * qty
                total_amount += subtotal

                spec_info = json.loads(sku.spec_info) if sku.spec_info else []
                spec_label = '/'.join([s.get('specValues', s.get('specValue', '')) for s in spec_info])
                imgs_raw = json.loads(spu.images) if spu.images else []
                thumb = get_image_display_url(imgs_raw[0]) if imgs_raw else ''

                order_items.append(OrderItem(
                    order_id=order_id,
                    spu_id=spu.spu_id,
                    sku_id=sku.sku_id,
                    title=spu.title,
                    thumb=thumb,
                    spec_label=spec_label,
                    price=price,
                    quantity=qty,
                    subtotal=subtotal,
                ))

            # 校验配送地址：优先按 addressId 从数据库加载，确保属于当前用户
            address_id = consignee.get('addressId', '')
            if address_id:
                address = session.query(UserAddress).filter(
                    UserAddress.id == address_id,
                    UserAddress.userid == user_id,
                ).first()
                if not address:
                    raise Fail("ADDRESS_NOT_FOUND", {}, "配送地址不存在或不属于当前用户")
                consignee_name = address.name
                consignee_mobile = address.mobile
                addr = '{} {} {}{}'.format(
                    address.province or '',
                    address.city or '',
                    address.district or '',
                    address.detail or '',
                ).strip()
            else:
                # 无 addressId 时使用前端传入的原始数据
                consignee_name = consignee.get('name', '')
                consignee_mobile = consignee.get('mobile', '')
                addr = '{} {} {}{}'.format(
                    consignee.get('province', ''),
                    consignee.get('city', ''),
                    consignee.get('district', ''),
                    consignee.get('detail', ''),
                ).strip()

            if delivery_type == 0 and (not consignee_name or not consignee_mobile):
                raise Fail("CONSIGNEE_REQUIRED", {}, "收货人姓名和手机号不能为空")

            # 计算运费
            freight_items = [{'spu_id': it['spuId'], 'quantity': it['quantity']} for it in items]
            freight_amount = FreightCalculator.calc(freight_items, province_code, total_amount)

            order = Order(
                order_id=order_id,
                user_id=user_id,
                total_amount=total_amount,
                freight_amount=freight_amount,
                pay_amount=total_amount + freight_amount,
                delivery_type=delivery_type,
                consignee_name=consignee_name,
                consignee_mobile=consignee_mobile,
                consignee_address=addr,
                remark=remark,
                pickup_store_id=pickup_store_id,
                pickup_store_name=pickup_store_name,
                local_delivery_time=local_delivery_time,
            )
            session.add(order)
            session.flush()  # 先插入 order，确保 order_id 可用
            for oi in order_items:
                session.add(oi)

            # 删除购物车中已下单的商品
            for it in items:
                session.query(Cart).filter(
                    Cart.user_id == user_id,
                    Cart.sku_id == it['skuId'],
                ).delete()

        return {
            'code': 'Success',
            'data': {
                'orderId': order_id,
                'payAmount': total_amount,
                'tradeNo': order_id,
                'channel': 'wechat',
                'payInfo': '',
                'interactId': '',
                'transactionId': '',
            },
        }

    @classmethod
    def get_detail(cls, order_pk, user_id):
        """获取订单详情（按主键 id 查询）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.id == order_pk,
                Order.user_id == user_id,
                Order.deleted == 0,
            ).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            items = session.query(OrderItem).filter(
                OrderItem.order_id == order.order_id
            ).all()
            return {
                'orderId': order.order_id,
                'orderNo': order.order_id,
                'orderStatus': order.order_status,
                'orderStatusName': cls._status_name(order.order_status),
                'paymentAmount': order.pay_amount,
                'goodsAmountApp': order.total_amount,
                'totalAmount': order.total_amount,
                'freightFee': order.freight_amount,
                'deliveryType': order.delivery_type,
                'consigneeName': order.consignee_name,
                'consigneeMobile': order.consignee_mobile,
                'consigneeAddress': order.consignee_address,
                'remark': order.remark,
                'paymentMethod': order.payment_method,
                'paidAt': cls._fmt_dt(order.paid_at),
                'shippedAt': cls._fmt_dt(order.shipped_at),
                'completedAt': cls._fmt_dt(order.completed_at),
                'canceledAt': cls._fmt_dt(order.canceled_at),
                'createTime': cls._fmt_dt(order.create_time),
                'logisticsVO': {'logisticsNo': ''},
                'buttonVOs': [],
                'orderItemVOs': [{
                    'id': oi.id,
                    'spuId': oi.spu_id,
                    'skuId': oi.sku_id,
                    'goodsName': oi.title,
                    'goodsPictureUrl': get_image_display_url(oi.thumb) if oi.thumb else '',
                    'specInfo': [{'specValue': oi.spec_label}],
                    'specifications': [{'specValue': oi.spec_label}],
                    'price': oi.price,
                    'tagPrice': None,
                    'actualPrice': oi.price,
                    'buyQuantity': oi.quantity,
                    'goodsCount': oi.quantity,
                } for oi in items],
            }

    @classmethod
    def cancel(cls, order_id, user_id):
        """取消订单，恢复库存"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.order_id == order_id,
                Order.user_id == user_id,
            ).with_for_update().first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            if order.order_status != 0:
                raise Fail("ORDER_CANNOT_CANCEL", {}, "当前订单状态不可取消")

            order.order_status = 4  # 已取消
            order.pay_status = 2 if order.pay_status == 1 else order.pay_status
            order.canceled_at = datetime.now()

            # 恢复库存
            items = session.query(OrderItem).filter(OrderItem.order_id == order_id).all()
            for oi in items:
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == oi.sku_id).with_for_update().first()
                if sku:
                    sku.stock_quantity += oi.quantity
                    # 实时联动恢复进销存库存（同一事务）：无条码或未匹配到进销存商品时跳过
                    InvGoodsDao.adjust_by_barcode(
                        session, sku.barcode, oi.quantity, order_id,
                        remark='取消订单恢复库存: 订单 {}'.format(order_id),
                    )

        return {'success': True}

    @classmethod
    def delete(cls, order_id, user_id):
        """删除订单（仅已完成/已取消可删除，软删除进回收站）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.order_id == order_id,
                Order.user_id == user_id,
            ).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            if order.order_status not in (3, 4):
                raise Fail("ORDER_CANNOT_DELETE", {}, "当前订单状态不可删除")
            order.deleted = 1
            order.deleted_at = datetime.now()
        return {'success': True}

    @classmethod
    def admin_delete(cls, order_id):
        """后台删除订单（不限制用户，仅已完成/已取消可删除，软删除进回收站）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            if order.order_status not in (3, 4):
                raise Fail("ORDER_CANNOT_DELETE", {}, "当前订单状态不可删除")
            order.deleted = 1
            order.deleted_at = datetime.now()
        return {'success': True}

    @classmethod
    def admin_recycle_list(cls, page_num=1, page_size=10, order_no=''):
        """回收站订单列表（已删除订单）"""
        session = get_session()
        with session.begin():
            q = session.query(Order).filter(Order.deleted == 1)
            if order_no:
                q = q.filter(Order.order_id.like('%' + order_no + '%'))
            total = q.count()
            q = q.order_by(Order.deleted_at.desc(), Order.create_time.desc()).limit(page_size).offset((page_num - 1) * page_size)
            orders = q.all()
            return {'data': {
                'total': total,
                'list': [cls._format_admin_order(o, session) for o in orders],
            }}

    @classmethod
    def admin_recycle_restore(cls, order_id):
        """回收站恢复订单"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            order.deleted = 0
            order.deleted_at = None
        return {'success': True}

    @classmethod
    def admin_recycle_purge(cls, order_id):
        """回收站彻底删除（物理删除订单及明细，不可恢复）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            session.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
            session.delete(order)
        return {'success': True}

    @classmethod
    def confirm(cls, order_id, user_id):
        """确认收货（待收货 → 已完成）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.order_id == order_id,
                Order.user_id == user_id,
            ).with_for_update().first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            if order.order_status != 2:
                raise Fail("ORDER_CANNOT_CONFIRM", {}, "当前订单状态不可确认收货")
            order.order_status = 3  # 已完成
            order.completed_at = datetime.now()
        return {'success': True}

    @classmethod
    def remind(cls, order_id, user_id):
        """提醒发货（仅待发货可提醒）"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.order_id == order_id,
                Order.user_id == user_id,
            ).with_for_update().first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            if order.order_status != 1:
                raise Fail("ORDER_CANNOT_REMIND", {}, "当前订单状态不可提醒发货")
        return {'success': True}
