"""进销存库存数据访问层"""
import json
import uuid
from datetime import datetime

from sqlalchemy import func, desc, or_

from mall.db.engines.mysql import get_session
from mall.db.models.Stock.model import InvGoods, StockInOrder, StockInItem, StockLog
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class InvGoodsDao:
    """进销存独立库存商品数据访问"""

    @staticmethod
    def _coerce_gds_raw(data):
        """把 GDS 原始数据转成 text 字段的 JSON 字符串。

        支持三种来源：
        - data['gds_raw'] / data['gdsRaw']: dict -> json.dumps
        - data['gds_raw'] / data['gdsRaw']: 已序列化的 str -> 原样返回
        - data['text']: 直接传的字符串
        """
        raw = data.get('gds_raw', data.get('gdsRaw', data.get('text', '')))
        if raw is None:
            return ''
        if isinstance(raw, dict):
            try:
                return json.dumps(raw, ensure_ascii=False)
            except Exception:
                return ''
        return str(raw)

    @staticmethod
    def _extract_image_url(data):
        """从 gds_raw/text 中提取商品图片 URL。

        优先使用 data['image_url']，否则从 GDS 原始 JSON 里解析 image_url。
        """
        direct = data.get('image_url')
        if direct:
            return str(direct)
        raw = data.get('gds_raw', data.get('gdsRaw', data.get('text', '')))
        if not raw:
            return ''
        try:
            if isinstance(raw, str):
                raw = json.loads(raw)
            if isinstance(raw, dict):
                url = raw.get('image_url') or raw.get('imageUrl')
                return str(url) if url else ''
        except Exception:
            return ''
        return ''

    @staticmethod
    def _extract_unit(data):
        """从 GDS 原始数据里提取单位。

        优先使用 data['unit']，否则从 gds_raw/text 里取 PackagingTypeCodeDescription（包装类型）。
        """
        direct = data.get('unit')
        if direct:
            return str(direct).strip()
        raw = data.get('gds_raw', data.get('gdsRaw', data.get('text', '')))
        if not raw:
            return ''
        try:
            if isinstance(raw, str):
                raw = json.loads(raw)
            if isinstance(raw, dict):
                unit = raw.get('PackagingTypeCodeDescription') or raw.get('packaging_type_code_description')
                return str(unit).strip() if unit else ''
        except Exception:
            return ''
        return ''

    @classmethod
    def _ean13_check_digit(cls, code12):
        """EAN-13 校验位算法：输入12位数字字符串，返回校验位(0-9)"""
        total = 0
        for i, ch in enumerate(code12):
            digit = int(ch)
            # 从左往右：奇数位(第1,3,...)权重3，偶数位权重1
            total += digit * (3 if i % 2 == 0 else 1)
        rem = total % 10
        return 0 if rem == 0 else 10 - rem

    @classmethod
    def gen_barcode(cls, seq):
        """按 123-000-000000-X 格式生成 13 位 EAN-13 条码（无分隔符）。

        结构：前缀123(3) + 部门码000(3) + 商品流水号(6，支持百万级) + 校验位(1)。
        """
        seq = int(seq)
        if seq < 0 or seq > 999999:
            seq = seq % 1000000
        body12 = '123' + '000' + str(seq).zfill(6)
        check = cls._ean13_check_digit(body12)
        return body12 + str(check)

    @classmethod
    def create(cls, data):
        """新增库存商品（条码为空时自动生成 EAN-13 唯一条码）"""
        session = get_session()
        with session.begin():
            # 条码为空时按 EAN-13 格式自动生成唯一条码
            barcode = data.get('barcode', '').strip()
            if not barcode:
                # 用当前最大商品 id +1 作为流水号，与自增 id 天然唯一不冲突
                max_id = session.query(func.max(InvGoods.id)).scalar() or 0
                seq = max_id + 1
                # 生成后校验唯一，冲突则 +1 重试（避免取模循环导致重复）
                for _ in range(1000000):
                    barcode = cls.gen_barcode(seq)
                    exists = session.query(InvGoods).filter(InvGoods.barcode == barcode).first()
                    if not exists:
                        break
                    seq += 1
                else:
                    return None, '无法生成唯一条码'

            # 条码唯一性校验（用户手动填写的条码仍需校验）
            else:
                exists = session.query(InvGoods).filter(InvGoods.barcode == barcode).first()
                if exists:
                    return None, '该条码已存在商品'
            goods = InvGoods(
                barcode=barcode,
                name=data.get('name', '').strip(),
                brand=data.get('brand', '').strip(),
                spec=data.get('spec', '').strip(),
                unit=cls._extract_unit(data),
                category=data.get('category', '').strip(),
                cost_price=data.get('cost_price', 0),
                sale_price=data.get('sale_price', 0),
                stock_quantity=data.get('stock_quantity', 0),
                warn_threshold=data.get('warn_threshold', 0),
                supplier=data.get('supplier', '').strip(),
                shelf_life_days=data.get('shelf_life_days', 0),
                image_url=cls._extract_image_url(data),
                remark=data.get('remark', ''),
                text=cls._coerce_gds_raw(data),
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
            if 'gds_raw' in data or 'gdsRaw' in data or 'text' in data:
                goods.text = cls._coerce_gds_raw(data)
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
    def adjust_by_barcode(cls, session, barcode, change_qty, biz_no, remark,
                          operator_id=0, operator_name=''):
        """在外部传入的 session 事务内按条码调整进销存库存并写流水。

        供商城下单/取消等业务在同一事务内实时联动进销存库存。
        - change_qty 为负表示扣减（销售出库），为正表示增加（恢复/冲正）。
        - 若条码为空或未匹配到进销存商品，返回 (None, '')，不抛异常，由调用方决定降级策略。
        返回 (goods, error)，goods 为 InvGoods 实例。
        """
        barcode = (barcode or '').strip()
        if not barcode:
            return None, ''
        goods = session.query(InvGoods).filter(
            InvGoods.barcode == barcode
        ).with_for_update().first()
        if not goods:
            return None, ''

        change_qty = int(change_qty or 0)
        if change_qty == 0:
            return goods, ''

        new_stock = goods.stock_quantity + change_qty
        if new_stock < 0:
            return None, '库存不足: {}'.format(barcode)

        goods.stock_quantity = new_stock

        log = StockLog(
            goods_id=goods.id,
            change_qty=change_qty,
            balance_after=new_stock,
            biz_type='stock_out' if change_qty < 0 else 'stock_in',
            biz_no=biz_no,
            operator_id=operator_id,
            operator_name=operator_name,
            remark=remark,
        )
        session.add(log)
        return goods, ''

    @classmethod
    def get_stock_by_barcodes(cls, session, barcodes):
        """按条码批量查询进销存库存，返回 {barcode: stock_quantity}。

        供商城列表/详情/购物车实时读取进销存真实库存，避免逐条 N+1 查询。
        """
        barcodes = [b for b in (barcodes or []) if b and str(b).strip()]
        if not barcodes:
            return {}
        rows = session.query(InvGoods.barcode, InvGoods.stock_quantity).filter(
            InvGoods.barcode.in_(barcodes)
        ).all()
        return {barcode: (stock or 0) for barcode, stock in rows}

    @classmethod
    def get_inv_info_by_barcodes(cls, session, barcodes):
        """按条码批量查询进销存商品信息，返回 {barcode: {name, stock}}。

        供商城列表展示 SKU 关联的进销存商品名与库存，避免逐条 N+1 查询。
        """
        barcodes = [b for b in (barcodes or []) if b and str(b).strip()]
        if not barcodes:
            return {}
        rows = session.query(
            InvGoods.barcode, InvGoods.name, InvGoods.stock_quantity
        ).filter(InvGoods.barcode.in_(barcodes)).all()
        return {barcode: {'name': name, 'stock': (stock or 0)} for barcode, name, stock in rows}

    @classmethod
    def delete(cls, goods_id):
        """删除商品，并级联删除其关联资源：
        1. 该商品的入库明细（t_mall_stock_in_item）
        2. 该商品的库存流水（t_mall_stock_log）
        3. 仅包含该商品的入库单（明细删空后为空单则删除主表记录）

        返回 {'deleted': True, 'hasStockRecord': bool}，hasStockRecord 用于前端提示。
        """
        session = get_session()
        with session.begin():
            goods = session.query(InvGoods).filter(InvGoods.id == goods_id).first()
            if not goods:
                return None, '商品不存在'

            # 1. 找出引用该商品的入库明细及其所属入库单
            items = session.query(StockInItem).filter(StockInItem.goods_id == goods_id).all()
            has_stock_record = bool(items)
            order_ids = set(i.order_id for i in items)

            # 2. 删除该商品的入库明细
            session.query(StockInItem).filter(StockInItem.goods_id == goods_id).delete()

            # 3. 删除该商品的库存流水
            session.query(StockLog).filter(StockLog.goods_id == goods_id).delete()

            # 4. 删除仅包含该商品的入库单（明细删空后无其他商品则为空单）
            for order_id in order_ids:
                remaining = session.query(StockInItem).filter(
                    StockInItem.order_id == order_id
                ).count()
                if remaining == 0:
                    session.query(StockInOrder).filter(StockInOrder.id == order_id).delete()

            # 5. 删除商品本身
            session.delete(goods)
            session.flush()
            return {'deleted': True, 'hasStockRecord': has_stock_record}, None

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
            'text': goods.text or '',
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
