"""云打印机打印流水数据模型

每次打印（自动/手动）记录一行：订单号、设备、飞鹅受理订单ID、打印状态。
飞鹅打印是异步的：提交成功(status=0)不代表打印完成，
通过回调/回查更新为 打印成功(status=1) 或 打印失败(status=2)。
"""
from datetime import datetime
from sqlalchemy import Column, String, SmallInteger, Text, DateTime
from mall.db.models.base import BASE, DbBase


class PrintLog(BASE, DbBase):
    """打印流水表"""
    __tablename__ = 't_mall_print_log'

    id = Column(String(32), primary_key=True, comment='UUID主键')
    order_no = Column(String(64), default='', comment='订单号')
    biz_type = Column(SmallInteger, default=1, comment='业务类型 1=订单小票 2=测试打印')
    printer_sn = Column(String(32), default='', comment='打印设备SN')
    feie_order_id = Column(String(64), default='', comment='飞鹅受理订单ID(Open_printMsg返回,回调匹配用)')
    status = Column(SmallInteger, default=0, comment='打印状态 0=已提交 1=打印成功 2=打印失败')
    message = Column(Text, default='', comment='失败原因/备注')
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)
