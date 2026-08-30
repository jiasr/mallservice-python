"""扫码备货记录数据访问层"""
from sqlalchemy import desc

from mall.db.engines.mysql import get_session
from mall.db.models.PickRecord.model import PickRecord


class PickRecordDao:
    """备货记录数据访问"""

    @staticmethod
    def _fmt(rec):
        return {
            'id': rec.id,
            'orderNo': rec.order_no,
            'itemCount': rec.item_count,
            'totalQuantity': rec.total_quantity,
            'operatorId': rec.operator_id,
            'operatorName': rec.operator_name or '',
            'remark': rec.remark or '',
            'createTime': rec.create_time.strftime('%Y-%m-%d %H:%M:%S') if rec.create_time else '',
        }

    @classmethod
    def get_by_order_no(cls, order_no):
        """按订单号查询备货记录（无则返回 None）"""
        session = get_session()
        with session.begin():
            rec = session.query(PickRecord).filter(
                PickRecord.order_no == order_no
            ).first()
            return cls._fmt(rec) if rec else None

    @classmethod
    def create(cls, order_no, item_count, total_quantity,
               operator_id=0, operator_name='', remark=''):
        """记录一次备货完成。同单已备货返回 (None, '该订单已备货')，否则返回 (记录, None)"""
        session = get_session()
        with session.begin():
            exists = session.query(PickRecord).filter(
                PickRecord.order_no == order_no
            ).first()
            if exists:
                return None, '该订单已备货'
            rec = PickRecord(
                order_no=order_no,
                item_count=item_count,
                total_quantity=total_quantity,
                operator_id=operator_id,
                operator_name=operator_name,
                remark=remark or '',
            )
            session.add(rec)
            session.flush()
            return cls._fmt(rec), None

    @classmethod
    def list(cls, page_index=1, page_size=10, order_no=''):
        """备货记录分页列表，按时间倒序"""
        session = get_session()
        with session.begin():
            query = session.query(PickRecord)
            if order_no:
                query = query.filter(PickRecord.order_no.like('%{}%'.format(order_no)))
            total = query.count()
            rows = query.order_by(desc(PickRecord.id)) \
                .offset((page_index - 1) * page_size) \
                .limit(page_size).all()
            return {
                'total': total,
                'list': [cls._fmt(r) for r in rows],
            }
