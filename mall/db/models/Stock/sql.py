"""进销存库存数据访问层"""
from datetime import datetime

from sqlalchemy import func, desc, or_

from mall.db.engines.mysql import get_session
from mall.db.models.Stock.model import InvGoods, StockInOrder, StockInItem, StockLog
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class InvGoodsDao:
    """进销存独立库存商品数据访问"""

    @classmethod
    def create(cls, data):
        """新增库存商品"""
        session = get_session()
        with session.begin():
            # 条码唯一性校验
            barcode = data.get('barcode', '').strip()
            exists = session.query(InvGoods).filter(InvGoods.barcode == barcode).first()
            if exists:
                return None, '该条码已存在商品'
            goods = InvGoods(
                barcode=barcode,
                name=data.get('name', '').strip(),
                brand=data.get('brand', '').strip(),
                spec=data.get('spec', '').strip(),
                unit=data.get('unit', '').strip(),
                category=data.get('category', '').strip(),
                cost_price=data.get('cost_price', 0),
                sale_price=data.get('sale_price', 0),
                stock_quantity=data.get('stock_quantity', 0),
                warn_threshold=data.get('warn_threshold', 0),
                supplier=data.get('supplier', '').strip(),
                shelf_life_days=data.get('shelf_life_days', 0),
                image_url=data.get('image_url', ''),
                remark=data.get('remark', ''),
                status=data.get('status', 1),
            )
            session.add(goods)
            session.flush()
            return cls._format(goods), None

    @classmethod
    def update(cls, goods_id, data):
        """修改库存商品"""
        session = get_session()
        with session.begin():
            goods = session.query(InvGoods).filter(InvGoods.id == goods_id).first()
            if not goods:
                return None, '商品不存在'
            # 条码唯一性校验（排除自身）
            barcode = data.get('barcode', '').strip()
            if barcode:
                exists = session.query(InvGoods).filter(
                    InvGoods.barcode == barcode, InvGoods.id != goods_id
                ).first()
                if exists:
                    return None, '该条码已存在商品'
            for field in ['barcode', 'name', 'brand', 'spec', 'unit', 'category',
                          'supplier', 'image_url', 'remark']:
                if field in data:
                    setattr(goods, field, data.get(field, ''))
            for field in ['cost_price', 'sale_price', 'warn_threshold', 'shelf_life_days', 'status']:
                if field in data:
                    setattr(goods, field, data.get(field, 0))
            session.flush()
            return cls._format(goods), None

    @classmethod
    def get_by_barcode(cls, barcode):
        """按条码查询商品（PDA扫码用）"""
        session = get_session()
        with session.begin():
            goods = session.query(InvGoods).filter(
                InvGoods.barcode == barcode
            ).first()
            if not goods:
                return None
            return cls._format(goods)

    @classmethod
    def delete(cls, goods_id):
        """删除商品。

        有入库记录/库存流水的商品也允许删除（物理删除），返回 has_stock_record 标记，
        供上层提示"该商品已有入库记录"。
        注意：数据库未对该商品定义外键约束，物理删除不会因外键失败。
        """
        session = get_session()
        with session.begin():
            goods = session.query(InvGoods).filter(InvGoods.id == goods_id).first()
            if not goods:
                return None, '商品不存在'
            # 检查是否有相关入库明细（仅用于提示，不阻止删除）
            has_item = session.query(StockInItem).filter(
                StockInItem.goods_id == goods_id
            ).first()
            session.delete(goods)
            session.flush()
            return {'deleted': True, 'hasStockRecord': bool(has_item)}, None

    @classmethod
    def get_by_id(cls, goods_id):
        """按ID查询商品"""
        session = get_session()
        with session.begin():
            goods = session.query(InvGoods).filter(InvGoods.id == goods_id).first()
            if not goods:
                return None
            return cls._format(goods)

    @classmethod
    def get_list(cls, page_index=1, page_size=20, keyword=None, category=None):
        """分页查询商品列表"""
        session = get_session()
        with session.begin():
            query = session.query(InvGoods)
            if keyword:
                like = f'%{keyword}%'
                query = query.filter(or_(
                    InvGoods.name.like(like),
                    InvGoods.barcode.like(like),
                    InvGoods.brand.like(like),
                ))
            if category:
                query = query.filter(InvGoods.category == category)

            total = query.count()
            query = query.order_by(InvGoods.id.desc())
            start = (page_index - 1) * page_size
            goods_list = query.limit(page_size).offset(start).all()

            return {
                'pageIndex': page_index,
                'pageSize': page_size,
                'totalCount': total,
                'list': [cls._format(g) for g in goods_list],
            }

    @classmethod
    def _format(cls, goods):
        """格式化商品数据"""
        return {
            'id': goods.id,
            'barcode': goods.barcode,
            'name': goods.name,
            'brand': goods.brand,
            'spec': goods.spec,
            'unit': goods.unit,
            'category': goods.category,
            'costPrice': float(goods.cost_price or 0),
            'salePrice': float(goods.sale_price or 0),
            'stockQuantity': goods.stock_quantity,
            'warnThreshold': goods.warn_threshold,
            'supplier': goods.supplier,
            'shelfLifeDays': goods.shelf_life_days,
            'imageUrl': goods.image_url,
            'remark': goods.remark,
            'status': goods.status,
            'createTime': goods.create_time.strftime('%Y-%m-%d %H:%M:%S') if goods.create_time else '',
        }


class StockInOrderDao:
    """入库单数据访问"""

    @staticmethod
    def _generate_order_no(session):
        """生成入库单号: RK + 年月日 + 4位流水"""
        today = datetime.now().strftime('%Y%m%d')
        prefix = f'RK{today}'
        last = session.query(StockInOrder).filter(
            StockInOrder.order_no.like(f'{prefix}%')
        ).order_by(StockInOrder.id.desc()).first()
        if last:
            seq = int(last.order_no[-4:]) + 1
        else:
            seq = 1
        return f'{prefix}{seq:04d}'

    @classmethod
    def create(cls, data):
        """创建入库单（草稿状态）"""
        session = get_session()
        with session.begin():
            order_no = cls._generate_order_no(session)
            order = StockInOrder(
                order_no=order_no,
                type=data.get('type', 1),
                total_quantity=0,
                total_amount=0,
                status=0,
                operator_id=data.get('operator_id', 0),
                operator_name=data.get('operator_name', ''),
                remark=data.get('remark', ''),
            )
            session.add(order)
            session.flush()

            items = data.get('items', [])
            total_qty = 0
            total_amt = 0
            for item in items:
                entry = StockInItem(
                    order_id=order.id,
                    goods_id=item.get('goods_id', 0),
                    quantity=item.get('quantity', 0),
                    cost_price=item.get('cost_price', 0),
                    batch_no=item.get('batch_no', ''),
                    remark=item.get('remark', ''),
                )
                session.add(entry)
                qty = item.get('quantity', 0)
                total_qty += qty
                total_amt += qty * (item.get('cost_price', 0) or 0)

            order.total_quantity = total_qty
            order.total_amount = total_amt
            session.flush()

            return cls._format_order(session, order)

    @classmethod
    def submit(cls, order_id, operator_id=0, operator_name=''):
        """提交入库单：更新商品库存 + 写入库存流水"""
        session = get_session()
        with session.begin():
            order = session.query(StockInOrder).filter(
                StockInOrder.id == order_id
            ).with_for_update().first()
            if not order:
                return None, '入库单不存在'
            if order.status != 0:
                return None, '入库单状态不是草稿，无法提交'

            items = session.query(StockInItem).filter(
                StockInItem.order_id == order.id
            ).all()

            for item in items:
                goods = session.query(InvGoods).filter(
                    InvGoods.id == item.goods_id
                ).with_for_update().first()
                if not goods:
                    return None, f'商品不存在: {item.goods_id}'

                old_stock = goods.stock_quantity
                goods.stock_quantity = old_stock + item.quantity

                # 写入库存流水
                log = StockLog(
                    goods_id=item.goods_id,
                    change_qty=item.quantity,
                    balance_after=goods.stock_quantity,
                    biz_type='stock_in',
                    biz_no=order.order_no,
                    operator_id=operator_id,
                    operator_name=operator_name,
                    remark=f'入库单提交: {order.order_no}',
                )
                session.add(log)

            order.status = 1
            order.operator_id = operator_id or order.operator_id
            order.operator_name = operator_name or order.operator_name
            session.flush()

            return cls._format_order(session, order), None

    @classmethod
    def cancel(cls, order_id):
        """取消入库单"""
        session = get_session()
        with session.begin():
            order = session.query(StockInOrder).filter(
                StockInOrder.id == order_id
            ).first()
            if not order:
                return None, '入库单不存在'
            if order.status != 0:
                return None, '入库单状态不是草稿，无法取消'
            order.status = 2
            session.flush()
            return cls._format_order(session, order), None

    @classmethod
    def get_list(cls, page_index=1, page_size=20, status=None, keyword=None):
        """分页查询入库单列表"""
        session = get_session()
        with session.begin():
            query = session.query(StockInOrder)
            if status is not None:
                query = query.filter(StockInOrder.status == int(status))
            if keyword:
                query = query.filter(StockInOrder.order_no.like(f'%{keyword}%'))

            total = query.count()
            query = query.order_by(StockInOrder.id.desc())
            start = (page_index - 1) * page_size
            orders = query.limit(page_size).offset(start).all()

            return {
                'pageIndex': page_index,
                'pageSize': page_size,
                'totalCount': total,
                'list': [cls._format_order(session, o) for o in orders],
            }

    @classmethod
    def get_detail(cls, order_id):
        """获取入库单详情（含明细）"""
        session = get_session()
        with session.begin():
            order = session.query(StockInOrder).filter(
                StockInOrder.id == order_id
            ).first()
            if not order:
                return None
            return cls._format_order(session, order, with_items=True)

    @classmethod
    def _format_order(cls, session, order, with_items=False):
        """格式化入库单数据"""
        result = order.to_dict()
        result['total_amount'] = float(order.total_amount or 0)
        if with_items:
            items = session.query(StockInItem).filter(
                StockInItem.order_id == order.id
            ).all()
            item_list = []
            for item in items:
                d = item.to_dict()
                d['cost_price'] = float(item.cost_price or 0)
                # 补充商品信息
                goods = session.query(InvGoods).filter(
                    InvGoods.id == item.goods_id
                ).first()
                if goods:
                    d['goods_barcode'] = goods.barcode
                    d['goods_name'] = goods.name
                    d['goods_spec'] = goods.spec
                    d['goods_unit'] = goods.unit
                    d['goods_brand'] = goods.brand
                else:
                    d['goods_name'] = ''
                    d['goods_barcode'] = ''
                item_list.append(d)
            result['items'] = item_list
        return result


class StockLogDao:
    """库存流水数据访问"""

    @classmethod
    def get_list(cls, goods_id=None, page_index=1, page_size=20, biz_type=None):
        """分页查询库存流水"""
        session = get_session()
        with session.begin():
            query = session.query(StockLog)
            if goods_id:
                query = query.filter(StockLog.goods_id == goods_id)
            if biz_type:
                query = query.filter(StockLog.biz_type == biz_type)

            total = query.count()
            query = query.order_by(StockLog.id.desc())
            start = (page_index - 1) * page_size
            logs = query.limit(page_size).offset(start).all()

            list_data = []
            for log in logs:
                d = log.to_dict()
                goods = session.query(InvGoods).filter(
                    InvGoods.id == log.goods_id
                ).first()
                d['goods_name'] = goods.name if goods else ''
                d['goods_barcode'] = goods.barcode if goods else ''
                list_data.append(d)

            return {
                'pageIndex': page_index,
                'pageSize': page_size,
                'totalCount': total,
                'list': list_data,
            }
