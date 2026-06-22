"""运费数据访问层"""
import math
from mall.db.engines.mysql import get_session
from mall.db.models.Freight.model import FreightTemplate, FreightRegion
from mall.db.models.Goods.model import GoodsSpu
from mall.common.common import Fail
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class FreightTemplateDao:

    @classmethod
    def list(cls, page_num=1, page_size=20):
        """模板列表"""
        session = get_session()
        with session.begin():
            q = session.query(FreightTemplate)
            total = q.count()
            q = q.order_by(FreightTemplate.create_time.desc()).limit(page_size).offset((page_num - 1) * page_size)
            return {
                'total': total,
                'list': [t.to_dict() for t in q.all()],
            }

    @classmethod
    def detail(cls, template_id):
        """模板详情（含地区规则）"""
        session = get_session()
        with session.begin():
            tmpl = session.query(FreightTemplate).filter(FreightTemplate.id == template_id).first()
            if not tmpl:
                raise Fail("TEMPLATE_NOT_FOUND", {}, "模板不存在")
            regions = session.query(FreightRegion).filter(
                FreightRegion.template_id == template_id
            ).all()
            result = tmpl.to_dict()
            result['regions'] = [r.to_dict() for r in regions]
            return result

    @classmethod
    def create(cls, data):
        """新增模板"""
        session = get_session()
        with session.begin():
            if data.get('is_default'):
                session.query(FreightTemplate).update({'is_default': 0})
            tmpl = FreightTemplate(
                name=data.get('name', ''),
                pricing_type=int(data.get('pricing_type', 1)),
                fixed_fee=int(data.get('fixed_fee', 0)),
                first_unit=int(data.get('first_unit', 1)),
                first_fee=int(data.get('first_fee', 0)),
                continue_unit=int(data.get('continue_unit', 1)),
                continue_fee=int(data.get('continue_fee', 0)),
                free_threshold=int(data.get('free_threshold', 0)),
                is_default=1 if data.get('is_default') else 0,
            )
            session.add(tmpl)
            session.flush()
            return {'id': tmpl.id}

    @classmethod
    def update(cls, template_id, data):
        """更新模板"""
        session = get_session()
        with session.begin():
            tmpl = session.query(FreightTemplate).filter(FreightTemplate.id == template_id).first()
            if not tmpl:
                raise Fail("TEMPLATE_NOT_FOUND", {}, "模板不存在")
            if data.get('is_default'):
                session.query(FreightTemplate).update({'is_default': 0})
            for field in ['name', 'pricing_type', 'fixed_fee', 'first_unit',
                          'first_fee', 'continue_unit', 'continue_fee',
                          'free_threshold']:
                if field in data:
                    setattr(tmpl, field, data[field])
            if 'is_default' in data:
                tmpl.is_default = 1 if data['is_default'] else 0
            return {'id': tmpl.id}

    @classmethod
    def delete(cls, template_id):
        """删除模板"""
        session = get_session()
        with session.begin():
            tmpl = session.query(FreightTemplate).filter(FreightTemplate.id == template_id).first()
            if not tmpl:
                raise Fail("TEMPLATE_NOT_FOUND", {}, "模板不存在")
            # 删除关联的地区规则
            session.query(FreightRegion).filter(
                FreightRegion.template_id == template_id
            ).delete()
            session.delete(tmpl)
            return {'success': True}

    @classmethod
    def set_default(cls, template_id):
        """设为默认模板"""
        session = get_session()
        with session.begin():
            session.query(FreightTemplate).update({'is_default': 0})
            tmpl = session.query(FreightTemplate).filter(FreightTemplate.id == template_id).first()
            if not tmpl:
                raise Fail("TEMPLATE_NOT_FOUND", {}, "模板不存在")
            tmpl.is_default = 1
            return {'success': True}

    @classmethod
    def get_default_template(cls):
        """获取系统默认模板"""
        session = get_session()
        with session.begin():
            tmpl = session.query(FreightTemplate).filter(
                FreightTemplate.is_default == 1
            ).first()
            return tmpl


class FreightRegionDao:

    @classmethod
    def list(cls, template_id):
        """获取模板的地区规则列表"""
        session = get_session()
        with session.begin():
            regions = session.query(FreightRegion).filter(
                FreightRegion.template_id == template_id
            ).all()
            return [r.to_dict() for r in regions]

    @classmethod
    def save(cls, template_id, regions):
        """批量保存地区规则（全量覆盖）"""
        session = get_session()
        with session.begin():
            # 删除旧规则
            session.query(FreightRegion).filter(
                FreightRegion.template_id == template_id
            ).delete()
            # 插入新规则
            for r in regions:
                reg = FreightRegion(
                    template_id=template_id,
                    region_code=r.get('regionCode', ''),
                    region_name=r.get('regionName', ''),
                    is_free=1 if r.get('isFree') else 0,
                    fixed_fee=r.get('fixedFee'),
                    first_fee=r.get('firstFee'),
                    continue_fee=r.get('continueFee'),
                    free_threshold=r.get('freeThreshold'),
                )
                session.add(reg)
            return {'success': True, 'count': len(regions)}

    @classmethod
    def get_region(cls, template_id, region_code):
        """获取某个省份的地区规则"""
        session = get_session()
        with session.begin():
            return session.query(FreightRegion).filter(
                FreightRegion.template_id == template_id,
                FreightRegion.region_code == region_code,
            ).first()


class FreightCalculator:
    """运费计算引擎"""

    @classmethod
    def calc(cls, items, province_code='', total_amount=0):
        """计算运费

        Args:
            items: 商品列表 [{'spu_id':..., 'quantity':...}, ...]
            province_code: 收货省份编码
            total_amount: 商品总金额(分)
        Returns:
            运费金额(分)
        """
        if not items:
            return 0

        # 1. 获取运费模板ID
        template_ids = set()
        session = get_session()
        with session.begin():
            for it in items:
                spu = session.query(GoodsSpu).filter(
                    GoodsSpu.spu_id == it.get('spu_id', '')
                ).first()
                tid = spu.freight_template_id if spu and spu.freight_template_id else 0
                template_ids.add(tid)

            # 2. 确定使用哪个模板
            if len(template_ids) == 0 or (len(template_ids) == 1 and 0 in template_ids):
                tmpl = session.query(FreightTemplate).filter(
                    FreightTemplate.is_default == 1
                ).first()
            elif len(template_ids) == 1:
                tid = template_ids.pop()
                tmpl = session.query(FreightTemplate).filter(
                    FreightTemplate.id == tid
                ).first()
            else:
                # 多种模板 → 取运费最高的那个
                tmpl = None
                max_fee = 0
                for tid in template_ids:
                    if tid == 0:
                        t = session.query(FreightTemplate).filter(
                            FreightTemplate.is_default == 1
                        ).first()
                    else:
                        t = session.query(FreightTemplate).filter(
                            FreightTemplate.id == tid
                        ).first()
                    if t:
                        fee = cls._estimate_fee(t, province_code, total_amount, items)
                        if fee > max_fee:
                            max_fee = fee
                            tmpl = t

            if not tmpl:
                return 0

            # 3. 获取地区规则
            region = None
            if province_code:
                region = session.query(FreightRegion).filter(
                    FreightRegion.template_id == tmpl.id,
                    FreightRegion.region_code == province_code,
                ).first()

            # 4. 判断包邮
            if region and region.is_free == 1:
                return 0
            threshold = region.free_threshold if (region and region.free_threshold is not None) else tmpl.free_threshold
            if threshold > 0 and total_amount >= threshold:
                return 0

            # 5. 计算运费
            total_qty = sum(it.get('quantity', 1) for it in items)

            if tmpl.pricing_type == 0:  # 固定运费
                fee = region.fixed_fee if (region and region.fixed_fee is not None) else tmpl.fixed_fee
                return fee
            else:  # 按件
                first_fee = region.first_fee if (region and region.first_fee is not None) else tmpl.first_fee
                cont_fee = region.continue_fee if (region and region.continue_fee is not None) else tmpl.continue_fee
                remain = max(0, total_qty - tmpl.first_unit)
                return first_fee + int(math.ceil(remain / tmpl.continue_unit)) * cont_fee

    @classmethod
    def _estimate_fee(cls, tmpl, province_code, total_amount, items):
        """估算某种模板的运费（用于多模板比较）"""
        region = None
        try:
            session = get_session()
            with session.begin():
                if province_code:
                    region = session.query(FreightRegion).filter(
                        FreightRegion.template_id == tmpl.id,
                        FreightRegion.region_code == province_code,
                    ).first()
        except Exception:
            pass

        if region and region.is_free == 1:
            return 0
        threshold = region.free_threshold if (region and region.free_threshold is not None) else tmpl.free_threshold
        if threshold > 0 and total_amount >= threshold:
            return 0
        total_qty = sum(it.get('quantity', 1) for it in items)

        if tmpl.pricing_type == 0:
            return region.fixed_fee if (region and region.fixed_fee is not None) else tmpl.fixed_fee
        else:
            first_fee = region.first_fee if (region and region.first_fee is not None) else tmpl.first_fee
            cont_fee = region.continue_fee if (region and region.continue_fee is not None) else tmpl.continue_fee
            remain = max(0, total_qty - tmpl.first_unit)
            return first_fee + int(math.ceil(remain / tmpl.continue_unit)) * cont_fee
