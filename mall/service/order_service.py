"""订单业务层"""
from datetime import datetime
from mall.db.models.Order.sql import OrderDao
from mall.db.models.Order.model import Order
from mall.db.models.User.model import User
from mall.db.engines.mysql import get_session
from mall.service.wechat_pay_service import WechatPayService
from mall.common.common import Fail
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


def check_pay(user_id, data):
    """主动查询微信支付状态并更新订单"""
    order_id = data.get('orderId', '')
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(
            Order.order_id == order_id,
            Order.user_id == user_id,
        ).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.pay_status == 1:
            return {'payStatus': 1, 'paidAt': order.paid_at.strftime('%Y-%m-%d %H:%M:%S') if order.paid_at else ''}

    try:
        result = WechatPayService.query_order(order_id)
        trade_state = result.get('trade_state', '')
        transaction_id = result.get('transaction_id', '')

        if trade_state == 'SUCCESS':
            session = get_session()
            with session.begin():
                ord = session.query(Order).filter(Order.order_id == order_id).first()
                if ord and ord.pay_status == 0:
                    ord.pay_status = 1
                    ord.order_status = 1
                    ord.paid_at = datetime.now()
                    ord.payment_method = 'wechat'
                    ord.transaction_id = transaction_id
            LOG.info("主动查询确认支付成功: {}".format(order_id))
            return {'payStatus': 1, 'paidAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        else:
            return {'payStatus': 0, 'tradeState': trade_state}
    except Exception as e:
        LOG.error("查询支付状态失败: {}".format(e))
        raise Fail("QUERY_FAIL", {}, str(e))


def preview(user_id, data):
    return OrderDao.preview(
        user_id,
        data.get('items', []),
        data.get('consignee', {}).get('provinceCode', ''),
        int(data.get('deliveryType', 0)),
    )


def create(user_id, data):
    return OrderDao.create(user_id, data)


def detail(user_id, order_id):
    return OrderDao.get_detail(order_id, user_id)


def cancel(user_id, data):
    return OrderDao.cancel(data.get('orderId', ''), user_id)


def order_list(user_id, params):
    return OrderDao.list(
        user_id,
        int(params.get('pageNum', 1)),
        int(params.get('pageSize', 10)),
        params.get('orderStatus'),
    )


def order_count(user_id):
    return OrderDao.count_by_status(user_id)


def admin_list(params):
    return OrderDao.admin_list(
        int(params.get('pageNum', 1)),
        int(params.get('pageSize', 10)),
        params.get('orderStatus'),
        params.get('orderNo', ''),
        params.get('consignee', ''),
        params.get('phone', ''),
    )


def admin_process(order_no, data):
    return OrderDao.admin_process(order_no, data)


def admin_detail(order_no):
    return OrderDao.admin_detail(order_no)


def pay(user_id, data):
    """获取微信支付参数"""
    order_id = data.get('orderId', '')
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(
            Order.order_id == order_id, Order.user_id == user_id
        ).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.pay_status != 0:
            raise Fail("ORDER_ALREADY_PAID", {}, "订单已支付")

        # 获取用户 OpenID
        user = session.query(User).filter(User.id == user_id).first()
        openid = user.wx_openid if user and user.wx_openid else ''
        if not openid:
            raise Fail("OPENID_NOT_FOUND", {}, "未获取到用户微信标识")

    try:
        pay_params = WechatPayService.get_pay_params(
            order_id, order.pay_amount, openid
        )
        LOG.info(pay_params)
    except Exception as e:
        err_msg = str(e)
        LOG.error("微信支付下单失败: {}".format(err_msg))
        raise Fail("PAY_FAIL", {}, err_msg)

    return {
        'orderId': order_id,
        'payAmount': order.pay_amount,
        'paySign': pay_params,
    }


def admin_refund(order_no, data):
    """管理员发起退款"""
    reason = data.get('reason', '')
    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_no).first()
        if not order:
            raise Fail("ORDER_NOT_FOUND", {}, "订单不存在")
        if order.pay_status != 1:
            raise Fail("ORDER_NOT_PAID", {}, "订单未支付或已退款")
        if not order.transaction_id:
            raise Fail("NO_TRANSACTION_ID", {}, "该订单无微信交易号，无法退款")

        refund_amount = order.pay_amount

    try:
        result = WechatPayService.refund(
            order_id=order_no,
            transaction_id=order.transaction_id,
            refund_amount=refund_amount,
            total_amount=order.pay_amount,
            reason=reason,
        )
    except Exception as e:
        LOG.error("退款失败: {}".format(e))
        raise Fail("REFUND_FAIL", {}, str(e))

    # 退款成功后更新订单状态
    session = get_session()
    with session.begin():
        ord = session.query(Order).filter(Order.order_id == order_no).first()
        if ord:
            ord.pay_status = 2
            ord.order_status = 4

    LOG.info("订单 {} 退款成功, 金额: {}分".format(order_no, refund_amount))
    return {'success': True, 'refundAmount': refund_amount}


def pay_notify_v3(body_json, headers):
    """微信支付 APIv3 回调处理"""
    try:
        result = WechatPayService.parse_notify(body_json, headers)
    except Exception as e:
        LOG.error("APIv3 回调处理失败: {}".format(e))
        return {'code': 'FAIL', 'message': str(e)}, 500

    if result.get('trade_state') != 'SUCCESS':
        LOG.warning("回调交易状态非 SUCCESS: {}".format(result.get('trade_state')))
        return {'code': 'FAIL', 'message': 'trade_state not SUCCESS'}, 500

    order_id = result.get('out_trade_no', '')
    transaction_id = result.get('transaction_id', '')

    session = get_session()
    with session.begin():
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if order and order.pay_status == 0:
            order.pay_status = 1
            order.order_status = 1
            order.paid_at = datetime.now()
            order.payment_method = 'wechat'
            order.transaction_id = transaction_id

    LOG.info("订单 {} 支付成功, 微信交易号: {}".format(order_id, transaction_id))
    return {'code': 'SUCCESS', 'message': 'OK'}
