"""用户协议与隐私政策数据访问层"""
import re

from mall.common.constant import SETTING_LIST_DEFAILT_PAGESIZE
from mall.db.engines.mysql import get_session
from mall.db.engines.s3 import get_image_display_url
from mall.db.models.Agreement.model import Agreement


class AgreementDao:
    """用户协议与隐私政策数据访问"""

    @staticmethod
    def _convert_desc_images(html):
        """把富文本HTML里相对路径图片(<img src='/...'>)转为完整公网URL，已含http/https的保持原样"""
        if not html:
            return html

        def _replace(m):
            prefix, quote, src = m.group(1), m.group(2), m.group(3)
            return '{}src={}{}{}'.format(prefix, quote, get_image_display_url(src), quote)

        pattern = re.compile(r'(\<img[^>]*\s)src=(["\'])(.*?)\2', re.IGNORECASE)
        return pattern.sub(_replace, html)

    @classmethod
    def _format(cls, row):
        if not row:
            return None
        return {
            'id': row.id,
            'type': row.type,
            'title': row.title,
            'content': cls._convert_desc_images(row.content or ''),
            'version': row.version,
            'status': row.status,
            'createTime': row.create_time.strftime('%Y-%m-%d %H:%M:%S') if row.create_time else '',
            'updateTime': row.update_time.strftime('%Y-%m-%d %H:%M:%S') if row.update_time else '',
        }

    @classmethod
    def list(cls, params):
        """后台配置：分页查询所有协议"""
        page_num = int(params.get('pageIndex', 1))
        page_size = int(params.get('pageSize', SETTING_LIST_DEFAILT_PAGESIZE))
        keyword = (params.get('keyword') or '').strip()
        agreement_type = (params.get('type') or '').strip()

        session = get_session()
        with session.begin():
            query = session.query(Agreement)
            if keyword:
                query = query.filter(Agreement.title.like('%{}%'.format(keyword)))
            if agreement_type:
                query = query.filter(Agreement.type == agreement_type)
            count = query.count()

            start = (page_num - 1) * page_size
            rows = query.order_by(Agreement.id.asc()).limit(page_size).offset(start).all()

        return count, [cls._format(r) for r in rows]

    @classmethod
    def get_by_type(cls, agreement_type):
        """小程序端：获取指定类型启用的协议"""
        session = get_session()
        with session.begin():
            row = session.query(Agreement).filter(
                Agreement.type == agreement_type,
                Agreement.status == 1,
            ).first()
        return cls._format(row)

    @classmethod
    def save(cls, data):
        """后台配置：新增或更新协议"""
        session = get_session()
        with session.begin():
            agreement_id = data.get('id')
            agreement_type = (data.get('type') or 'agreement').strip()
            row = None
            if agreement_id:
                row = session.query(Agreement).filter(Agreement.id == agreement_id).first()
            if not row:
                # 按类型查找已有记录，存在则更新
                row = session.query(Agreement).filter(Agreement.type == agreement_type).first()
            if row:
                row.type = agreement_type
                row.title = (data.get('title') or '').strip()
                row.content = data.get('content') or ''
                row.version = (data.get('version') or '1.0').strip()
                row.status = int(data.get('status', 1))
            else:
                row = Agreement(
                    type=agreement_type,
                    title=(data.get('title') or '').strip(),
                    content=data.get('content') or '',
                    version=(data.get('version') or '1.0').strip(),
                    status=int(data.get('status', 1)),
                )
                session.add(row)
            session.flush()
            return cls._format(row), None

    @classmethod
    def delete(cls, agreement_id):
        """后台配置：删除协议"""
        session = get_session()
        with session.begin():
            row = session.query(Agreement).filter(Agreement.id == agreement_id).first()
            if not row:
                return False, '协议不存在'
            session.delete(row)
            return True, ''
