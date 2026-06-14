"""订单数据访问层"""
import json
from datetime import datetime
from sqlalchemy import func
from mall.db.engines.mysql import get_session
from mall.db.models.Order.model import Order, OrderItem
from mall.db.models.Goods.model import GoodsSpu, GoodsSku
from mall.db.models.Cart.model import Cart
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
    """生成订单号: CH{年月日}{8位流水}"""
    prefix = datetime.now().strftime('CH%Y%m%d')
    max_id = session.query(func.max(Order.order_id)).filter(
        Order.order_id.like(prefix + '%')
    ).scalar()
    seq = int(max_id[-8:]) + 1 if max_id and len(max_id) >= 16 else 1
    return '{}{:08d}'.format(prefix, seq)


class OrderDao:

    @classmethod
    def preview(cls, user_id, items):
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
                if sku.stock_quantity <= 0:
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
        return {
            'totalAmount': total,
            'discountAmount': 0,
            'freightAmount': 0,
            'payAmount': total,
            'items': result_items,
        }

    @classmethod
    def create(cls, user_id, data):
        """创建订单（库存扣减使用悲观锁）"""
        items = data.get('items', [])
        consignee = data.get('consignee', {})
        remark = data.get('remark', '')

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
                if sku.stock_quantity < qty:
                    raise Fail("STOCK_NOT_ENOUGH", {}, "{} 库存不足".format(spu.title))

                # 扣减库存
                sku.stock_quantity -= qty
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

            addr = '{} {} {}{}'.format(
                consignee.get('province', ''),
                consignee.get('city', ''),
                consignee.get('district', ''),
                consignee.get('detail', ''),
            ).strip()

            order = Order(
                order_id=order_id,
                user_id=user_id,
                total_amount=total_amount,
                pay_amount=total_amount,
                consignee_name=consignee.get('name', ''),
                consignee_mobile=consignee.get('mobile', ''),
                consignee_address=addr,
                remark=remark,
            )
            session.add(order)
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
                'channel': '',
                'payInfo': '',
                'interactId': '',
                'transactionId': '',
            },
        }

    @classmethod
    def get_detail(cls, order_id, user_id):
        """获取订单详情"""
        session = get_session()
        with session.begin():
            order = session.query(Order).filter(
                Order.order_id == order_id,
                Order.user_id == user_id,
            ).first()
            if not order:
                raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
            items = session.query(OrderItem).filter(
                OrderItem.order_id == order_id
            ).all()
            return {
                'orderId': order.order_id,
                'totalAmount': order.total_amount,
                'discountAmount': order.discount_amount,
                'freightAmount': order.freight_amount,
                'payAmount': order.pay_amount,
                'payStatus': order.pay_status,
                'orderStatus': order.order_status,
                'consigneeName': order.consignee_name,
                'consigneeMobile': order.consignee_mobile,
                'consigneeAddress': order.consignee_address,
                'remark': order.remark,
                'paymentMethod': order.payment_method,
                'paidAt': order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else '',
                'createTime': order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else '',
                'items': [{
                    'spuId': oi.spu_id,
                    'skuId': oi.sku_id,
                    'title': oi.title,
                    'thumb': oi.thumb,
                    'specLabel': oi.spec_label,
                    'price': oi.price,
                    'quantity': oi.quantity,
                    'subtotal': oi.subtotal,
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

            # 恢复库存
            items = session.query(OrderItem).filter(OrderItem.order_id == order_id).all()
            for oi in items:
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == oi.sku_id).with_for_update().first()
                if sku:
                    sku.stock_quantity += oi.quantity

        return {'success': True}
