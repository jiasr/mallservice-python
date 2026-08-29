"""购物车数据访问层"""
import json
from sqlalchemy import func
from mall.db.engines.mysql import get_session
from mall.db.models.Cart.model import Cart
from mall.db.models.Goods.model import GoodsSpu, GoodsSku
from mall.db.models.Stock.sql import InvGoodsDao
from mall.db.engines.s3 import get_image_display_url
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class CartDao:

    # 购物车数量上限约束（设计文档第9章）
    MAX_PER_ADD = 99      # 单次加购最大数量
    MAX_PER_SKU = 999     # 单个 SKU 在购物车中的最大数量
    MAX_CART_ITEMS = 200  # 购物车商品总件数上限

    @staticmethod
    def _img_url(path):
        if not path:
            return ''
        images = json.loads(path) if path else []
        if isinstance(images, list) and len(images) > 0:
            return get_image_display_url(images[0])
        return get_image_display_url(path) if path else ''

    @classmethod
    def get_user_cart(cls, user_id):
        """获取用户购物车，同时校验商品有效性（批量查询避免 N+1）

        返回项附带该 SPU 的完整 skuList（规格切换弹窗数据源，仅有效商品带）。
        """
        session = get_session()
        with session.begin():
            items = session.query(Cart).filter(Cart.user_id == user_id).all()
            if not items:
                return {'validItems': [], 'invalidItems': [], 'selectedPrice': 0, 'selectedCount': 0}

            # 批量查询 SPU / SKU / 进销存库存，避免逐条 N+1
            spu_ids = [it.spu_id for it in items]
            sku_ids = [it.sku_id for it in items]
            spu_map = {s.spu_id: s for s in
                       session.query(GoodsSpu).filter(GoodsSpu.spu_id.in_(spu_ids)).all()}
            sku_map = {s.sku_id: s for s in
                       session.query(GoodsSku).filter(GoodsSku.sku_id.in_(sku_ids)).all()}

            barcodes = [sku_map[sid].barcode for sid in sku_ids if sid in sku_map]
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, barcodes)

            # 规格切换数据：批量查询涉及 SPU 的全部 SKU 及库存
            all_spus_sku = session.query(GoodsSku).filter(GoodsSku.spu_id.in_(spu_ids)).all()
            all_spus_barcodes = [s.barcode for s in all_spus_sku]
            all_inv_map = InvGoodsDao.get_stock_by_barcodes(session, all_spus_barcodes)
            sku_list_by_spu = {}
            for s in all_spus_sku:
                s_spec = json.loads(s.spec_info) if s.spec_info else []
                sku_list_by_spu.setdefault(s.spu_id, []).append({
                    'skuId': s.sku_id,
                    'price': s.price,
                    'stock': all_inv_map.get(s.barcode or '', s.stock_quantity or 0),
                    'specInfo': s_spec,
                })

            valid_items = []
            invalid_items = []

            for item in items:
                spu = spu_map.get(item.spu_id)
                sku = sku_map.get(item.sku_id)

                # SKU 或 SPU 不存在 → 自动删除
                if not spu or not sku:
                    session.delete(item)
                    continue

                # 实时读取进销存真实库存（按条码反查，无匹配则退回 SKU 库存）
                real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)

                # SPU 下架
                if spu.is_put_on_sale == 0 or spu.is_available == 0:
                    invalid_items.append(cls._build_item(item, spu, sku, real_stock, '商品已下架'))
                    continue

                # 库存为 0
                if real_stock <= 0 or spu.is_sold_out:
                    invalid_items.append(cls._build_item(item, spu, sku, real_stock, '商品已售罄'))
                    continue

                # 数量超库存 → 修正
                if item.quantity > real_stock:
                    item.quantity = real_stock
                    session.flush()
                    if real_stock <= 0:
                        invalid_items.append(cls._build_item(item, spu, sku, real_stock, '库存不足'))
                    else:
                        valid_items.append(cls._build_item(
                            item, spu, sku, real_stock, None, sku_list_by_spu.get(spu.spu_id)))
                        continue

                valid_items.append(cls._build_item(
                    item, spu, sku, real_stock, None, sku_list_by_spu.get(spu.spu_id)))

            selected_price = sum(it['price'] * it['quantity'] for it in valid_items if it.get('isSelected'))
            selected_count = sum(it['quantity'] for it in valid_items if it.get('isSelected'))

            return {
                'validItems': valid_items,
                'invalidItems': invalid_items,
                'selectedPrice': selected_price,
                'selectedCount': selected_count,
                'version': cls.get_cart_version(session, user_id),
            }

    @classmethod
    def _build_item(cls, cart_item, spu, sku, real_stock=None, invalid_reason=None, sku_list=None):
        """构建购物车项（sku_list 为该 SPU 完整规格数据，供规格切换弹窗使用）"""
        spec_info = json.loads(sku.spec_info) if sku.spec_info else []
        spec_label = '/'.join([s.get('specValues', s.get('specValue', '')) for s in spec_info])

        imgs = json.loads(spu.images) if spu.images else []
        thumb = get_image_display_url(imgs[0]) if imgs else ''

        if real_stock is None:
            real_stock = sku.stock_quantity or 0

        item = {
            'cartId': cart_item.id,
            'spuId': spu.spu_id,
            'skuId': sku.sku_id,
            'title': spu.title,
            'thumb': thumb,
            'specLabel': spec_label,
            'specInfo': spec_info,
            'price': sku.price,
            'stock': real_stock,
            'quantity': cart_item.quantity,
            'isSelected': bool(cart_item.is_selected),
        }
        if sku_list:
            item['skuList'] = sku_list
        if invalid_reason:
            item['invalidReason'] = invalid_reason
        return item

    @classmethod
    def get_cart_version(cls, session, user_id):
        """用户级购物车版本号（取所有购物车项的最大版本，无记录为 0）"""
        return int(session.query(func.max(Cart.cart_version)).filter(
            Cart.user_id == user_id).scalar() or 0)

    @classmethod
    def _bump_version(cls, session, user_id):
        """用户级购物车版本号 +1（统一写为 max+1，保证用户级单调递增）"""
        items = session.query(Cart).filter(Cart.user_id == user_id).all()
        if not items:
            return
        new_version = max(it.cart_version or 0 for it in items) + 1
        for it in items:
            it.cart_version = new_version

    @classmethod
    def _switch_sku(cls, session, item, new_sku_id, user_id):
        """购物车项换规格：目标 SKU 已存在则合并数量并删除当前项，否则原地更换"""
        new_sku = session.query(GoodsSku).filter(GoodsSku.sku_id == new_sku_id).first()
        if not new_sku:
            return {'status': 'error', 'message': 'SKU不存在'}
        inv_map = InvGoodsDao.get_stock_by_barcodes(session, [new_sku.barcode])
        real_stock = inv_map.get(new_sku.barcode or '', new_sku.stock_quantity or 0)
        if real_stock <= 0:
            return {'status': 'error', 'message': '商品已售罄'}

        existing = session.query(Cart).filter(
            Cart.user_id == user_id, Cart.sku_id == new_sku_id, Cart.id != item.id
        ).first()
        if existing:
            new_qty = existing.quantity + item.quantity
            if new_qty > real_stock:
                return {'status': 'error', 'message': '库存不足，最多可购买{}件'.format(real_stock)}
            if new_qty > cls.MAX_PER_SKU:
                return {'status': 'error', 'message': '单个商品最多购买{}件'.format(cls.MAX_PER_SKU)}
            existing.quantity = new_qty
            session.delete(item)
            return {'status': 'merged', 'cartId': existing.id}
        item.sku_id = new_sku_id
        item.spu_id = new_sku.spu_id
        return {'status': 'updated'}

    @classmethod
    def add_to_cart(cls, user_id, spu_id, sku_id, quantity=1):
        """加入购物车（已存在则叠加数量）"""
        session = get_session()
        with session.begin():
            # 单次加购数量上限
            if quantity <= 0 or quantity > cls.MAX_PER_ADD:
                return {'success': False, 'message': '单次最多购买{}件'.format(cls.MAX_PER_ADD)}

            # 校验库存
            sku = session.query(GoodsSku).filter(GoodsSku.sku_id == sku_id).first()
            if not sku:
                return {'success': False, 'message': 'SKU不存在'}
            # 实时读取进销存真实库存
            inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
            real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
            if real_stock <= 0:
                return {'success': False, 'message': '商品已售罄'}

            # 购物车总件数上限
            total_cart = int(session.query(func.sum(Cart.quantity)).filter(
                Cart.user_id == user_id).scalar() or 0)
            if total_cart + quantity > cls.MAX_CART_ITEMS:
                return {'success': False, 'message': '购物车已满，最多{}件商品'.format(cls.MAX_CART_ITEMS)}

            existing = session.query(Cart).filter(
                Cart.user_id == user_id, Cart.sku_id == sku_id
            ).first()

            if existing:
                new_qty = existing.quantity + quantity
                if new_qty > real_stock:
                    return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                if new_qty > cls.MAX_PER_SKU:
                    return {'success': False, 'message': '单个商品最多购买{}件'.format(cls.MAX_PER_SKU)}
                existing.quantity = new_qty
            else:
                if quantity > real_stock:
                    return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                cart_item = Cart(
                    user_id=user_id, spu_id=spu_id, sku_id=sku_id, quantity=quantity
                )
                session.add(cart_item)

            total = int(session.query(func.sum(Cart.quantity)).filter(Cart.user_id == user_id).scalar() or 0)
            cls._bump_version(session, user_id)
            return {
                'success': True,
                'cartCount': total,
                'version': cls.get_cart_version(session, user_id),
            }

    @classmethod
    def update_cart(cls, user_id, data):
        """更新数量/选中状态/换规格

        data 支持：cartId + {quantity?, isSelected?, skuId?}
        skuId 存在且不同 → 换规格；目标 SKU 已存在则合并（merged=true 返回新 cartId）
        """
        session = get_session()
        with session.begin():
            cart_id = data.get('cartId')
            item = session.query(Cart).filter(
                Cart.id == cart_id, Cart.user_id == user_id
            ).first()
            if not item:
                return {'success': False, 'message': '购物车项不存在'}

            # 换规格：优先处理（merged 时 item 已删除，后续字段变更不再应用）
            if data.get('skuId') and data['skuId'] != item.sku_id:
                result = cls._switch_sku(session, item, data['skuId'], user_id)
                if result['status'] == 'error':
                    return {'success': False, 'message': result['message']}
                cls._bump_version(session, user_id)
                total = int(session.query(func.sum(Cart.quantity)).filter(
                    Cart.user_id == user_id).scalar() or 0)
                if result['status'] == 'merged':
                    return {
                        'success': True,
                        'merged': True,
                        'cartId': result['cartId'],
                        'cartCount': total,
                        'version': cls.get_cart_version(session, user_id),
                    }
                # updated：继续应用数量/选中（fall through）

            if 'quantity' in data:
                qty = int(data['quantity'])
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == item.sku_id).first()
                if qty <= 0:
                    session.delete(item)
                    cls._bump_version(session, user_id)
                    total = int(session.query(func.sum(Cart.quantity)).filter(
                        Cart.user_id == user_id).scalar() or 0)
                    return {
                        'success': True,
                        'cartCount': total,
                        'version': cls.get_cart_version(session, user_id),
                    }
                if qty > cls.MAX_PER_SKU:
                    return {'success': False, 'message': '单个商品最多购买{}件'.format(cls.MAX_PER_SKU)}
                if sku:
                    # 实时读取进销存真实库存
                    inv_stock_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
                    real_stock = inv_stock_map.get(sku.barcode or '', sku.stock_quantity or 0)
                    if qty > real_stock:
                        return {'success': False, 'message': f'库存不足，最多可购买{real_stock}件'}
                item.quantity = qty

            if 'isSelected' in data:
                item.is_selected = 1 if data['isSelected'] else 0

            cls._bump_version(session, user_id)
            total = int(session.query(func.sum(Cart.quantity)).filter(
                Cart.user_id == user_id).scalar() or 0)
            return {
                'success': True,
                'cartCount': total,
                'version': cls.get_cart_version(session, user_id),
            }

    @classmethod
    def sync_cart(cls, user_id, items, client_version):
        """批量同步购物车变更（乐观锁）

        items: [{cartId, quantity?, isSelected?, skuId?, delete?}]
        client_version 与当前版本不匹配 → 返回 VERSION_CONFLICT（前端拉最新合并）
        """
        session = get_session()
        with session.begin():
            current_version = cls.get_cart_version(session, user_id)
            if current_version != client_version:
                return {
                    'success': False,
                    'code': 'VERSION_CONFLICT',
                    'message': '购物车已在其他设备修改，已为你刷新',
                    'version': current_version,
                }

            if not items:
                return {
                    'success': True,
                    'version': current_version,
                    'cartCount': int(session.query(func.sum(Cart.quantity)).filter(
                        Cart.user_id == user_id).scalar() or 0),
                }

            for op in items:
                cart_id = op.get('cartId')
                if not cart_id:
                    continue
                item = session.query(Cart).filter(
                    Cart.id == cart_id, Cart.user_id == user_id
                ).first()
                if not item:
                    continue
                # 兼容前端字段名：delete / deleted
                if op.get('delete') or op.get('deleted'):
                    session.delete(item)
                    continue
                # 换规格
                if op.get('skuId') and op['skuId'] != item.sku_id:
                    result = cls._switch_sku(session, item, op['skuId'], user_id)
                    if result['status'] == 'error':
                        return {'success': False, 'message': result['message']}
                    if result['status'] == 'merged':
                        continue
                if 'quantity' in op:
                    qty = int(op['quantity'])
                    if qty <= 0:
                        session.delete(item)
                        continue
                    if qty > cls.MAX_PER_SKU:
                        return {'success': False, 'message': '单个商品最多购买{}件'.format(cls.MAX_PER_SKU)}
                    item.quantity = qty
                if 'isSelected' in op:
                    item.is_selected = 1 if op['isSelected'] else 0

            cls._bump_version(session, user_id)
            total = int(session.query(func.sum(Cart.quantity)).filter(
                Cart.user_id == user_id).scalar() or 0)
            return {
                'success': True,
                'version': cls.get_cart_version(session, user_id),
                'cartCount': total,
            }

    @classmethod
    def delete_cart(cls, user_id, data):
        """删除购物车项"""
        session = get_session()
        with session.begin():
            cart_ids = data.get('cartIds') or [data.get('cartId')]
            for cid in cart_ids:
                item = session.query(Cart).filter(
                    Cart.id == cid, Cart.user_id == user_id
                ).first()
                if item:
                    session.delete(item)
            cls._bump_version(session, user_id)
            total = int(session.query(func.sum(Cart.quantity)).filter(
                Cart.user_id == user_id).scalar() or 0)
            return {
                'success': True,
                'cartCount': total,
                'version': cls.get_cart_version(session, user_id),
            }

    @classmethod
    def clear_cart(cls, user_id):
        """清空购物车"""
        session = get_session()
        with session.begin():
            session.query(Cart).filter(Cart.user_id == user_id).delete()
            return {'success': True, 'version': 0}

    @classmethod
    def merge_guest_cart(cls, user_id, items):
        """登录后合并游客本地购物车（同 SKU 叠加数量，受上限/库存约束）

        items: [{spuId, skuId, quantity}]
        """
        session = get_session()
        with session.begin():
            merged_count = 0
            total_items = 0
            for g in items:
                quantity = int(g.get('quantity') or 1)
                if quantity <= 0 or quantity > cls.MAX_PER_ADD:
                    continue
                sku = session.query(GoodsSku).filter(GoodsSku.sku_id == g.get('skuId')).first()
                if not sku:
                    continue
                inv_map = InvGoodsDao.get_stock_by_barcodes(session, [sku.barcode])
                real_stock = inv_map.get(sku.barcode or '', sku.stock_quantity or 0)
                if real_stock <= 0:
                    continue

                existing = session.query(Cart).filter(
                    Cart.user_id == user_id, Cart.sku_id == sku.sku_id
                ).first()
                if existing:
                    new_qty = existing.quantity + quantity
                    if new_qty > real_stock:
                        new_qty = real_stock
                    if new_qty > cls.MAX_PER_SKU:
                        new_qty = cls.MAX_PER_SKU
                    merged_count += new_qty - existing.quantity
                    existing.quantity = new_qty
                else:
                    qty = min(quantity, real_stock, cls.MAX_PER_SKU)
                    if qty <= 0:
                        continue
                    session.add(Cart(
                        user_id=user_id,
                        spu_id=sku.spu_id,
                        sku_id=sku.sku_id,
                        quantity=qty,
                    ))
                    merged_count += qty

            cls._bump_version(session, user_id)
            total_items = int(session.query(func.sum(Cart.quantity)).filter(
                Cart.user_id == user_id).scalar() or 0)
            return {
                'success': True,
                'mergedCount': merged_count,
                'cartCount': total_items,
                'version': cls.get_cart_version(session, user_id),
            }
