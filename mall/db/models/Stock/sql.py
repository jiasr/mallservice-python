"""库存数据访问层"""
import uuid
from datetime import datetime

from sqlalchemy import func, desc

from mall.db.engines.mysql import get_session
from mall.db.models.Stock.model import StockInOrder, StockInItem, StockLog
from mall.db.models.Goods.model import GoodsSku, GoodsSpu
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


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
                status=0,
                operator_id=data.get('operator_id', 0),
                operator_name=data.get('operator_name', ''),
                remark=data.get('remark', ''),
            )
            session.add(order)
            session.flush()

            items = data.get('items', [])
            total_qty = 0
            for item in items:
                entry = StockInItem(
                    order_id=order.id,
                    sku_id=item.get('sku_id', ''),
                    spu_id=item.get('spu_id', ''),
                    quantity=item.get('quantity', 0),
                    batch_no=item.get('batch_no', ''),
                    remark=item.get('remark', ''),
                )
                session.add(entry)
                total_qty += item.get('quantity', 0)

            order.total_quantity = total_qty
            session.flush()

            return cls._format_order(session, order)

    @classmethod
    def submit(cls, order_id, operator_id=0, operator_name=''):
        """提交入库单：更新SKU库存 + 写入库存流水"""
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
                sku = session.query(GoodsSku).filter(
                    GoodsSku.id == item.sku_id
                ).with_for_update().first()
                if not sku:
                    return None, f'SKU不存在: {item.sku_id}'

                old_stock = sku.stock_quantity
                sku.stock_quantity = old_stock + item.quantity

                # 更新SPU总库存
                spu = session.query(GoodsSpu).filter(
                    GoodsSpu.id == item.spu_id
                ).first()
                if spu:
                    spu.stock_quantity = spu.stock_quantity + item.quantity

                # 写入库存流水
                log = StockLog(
                    sku_id=item.sku_id,
                    spu_id=item.spu_id,
                    change_qty=item.quantity,
                    balance_after=sku.stock_quantity,
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
        if with_items:
            items = session.query(StockInItem).filter(
                StockInItem.order_id == order.id
            ).all()
            item_list = []
            for item in items:
                d = item.to_dict()
                # 补充SKU信息
                sku = session.query(GoodsSku).filter(
                    GoodsSku.id == item.sku_id
                ).first()
                if sku:
                    d['sku_barcode'] = sku.barcode or ''
                    d['sku_price'] = sku.price or 0
                    # 获取SPU标题
                    spu = session.query(GoodsSpu).filter(
                        GoodsSpu.id == item.spu_id
                    ).first()
                    d['spu_title'] = spu.title if spu else ''
                item_list.append(d)
            result['items'] = item_list
        return result


class StockLogDao:
    """库存流水数据访问"""

    @classmethod
    def get_list(cls, sku_id=None, page_index=1, page_size=20, biz_type=None):
        """分页查询库存流水"""
        session = get_session()
        with session.begin():
            query = session.query(StockLog)
            if sku_id:
                query = query.filter(StockLog.sku_id == sku_id)
            if biz_type:
                query = query.filter(StockLog.biz_type == biz_type)

            total = query.count()
            query = query.order_by(StockLog.id.desc())
            start = (page_index - 1) * page_size
            logs = query.limit(page_size).offset(start).all()

            return {
                'pageIndex': page_index,
                'pageSize': page_size,
                'totalCount': total,
                'list': [log.to_dict() for log in logs],
            }
