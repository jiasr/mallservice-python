"""订单 API 路由"""
import json
from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.common.common import deco_catch_view_exception, admin_required
from mall.service import order_service, pick_service

app_order = Blueprint('order', __name__)
ns_order = Namespace("order", description="订单", path="/v1/order")
LOG = logging.getLogger(__name__)


def _get_user_id():
    user_id = request.headers.get('token', '') or request.headers.get('userid', '')
    return user_id if user_id else None


@ns_order.route('/list', methods=['GET'])
class OrderList(Resource):
    @deco_catch_view_exception("订单列表")
    def get(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        import json as j
        data = j.loads(request.args.get('parameter', '{}'))
        return order_service.order_list(user_id, data)


@ns_order.route('/count', methods=['GET'])
class OrderCount(Resource):
    @deco_catch_view_exception("订单数量")
    def get(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        return order_service.order_count(user_id)


@ns_order.route('/preview', methods=['POST'])
class OrderPreview(Resource):
    @deco_catch_view_exception("订单预览")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.preview(user_id, data)


@ns_order.route('/create', methods=['POST'])
class OrderCreate(Resource):
    @deco_catch_view_exception("创建订单")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.create(user_id, data)


@ns_order.route('/detail', methods=['GET'])
class OrderDetail(Resource):
    @deco_catch_view_exception("订单详情")
    def get(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        order_id = request.args.get('id', 0)
        return order_service.detail(user_id, int(order_id))


@ns_order.route('/pay', methods=['POST'])
class OrderPay(Resource):
    """获取微信支付参数"""
    @deco_catch_view_exception("获取支付参数")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.pay(user_id, data)


@ns_order.route('/check-pay', methods=['POST'])
class OrderCheckPay(Resource):
    """主动查询支付状态"""
    @deco_catch_view_exception("查询支付状态")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.check_pay(user_id, data)


@ns_order.route('/pay/notify', methods=['POST'])
class OrderPayNotify(Resource):
    """微信支付 APIv3 回调通知"""
    # @deco_catch_view_exception("支付回调")
    def post(self):
        # APIv3: 请求体为 JSON，需要 headers 中的 Wechatpay-* 验签信息
        raw_body = request.get_data(as_text=True)
        body_json = request.get_json(force=True, silent=True) or {}
        try:
            order_service.pay_notify_v3(body_json, dict(request.headers), raw_body)
        except:
            LOG.info("sssss")

        return 'recived'

@ns_order.route('/cancel', methods=['POST'])
class OrderCancel(Resource):
    @deco_catch_view_exception("取消订单")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.cancel(user_id, data)


@ns_order.route('/delete', methods=['POST'])
class OrderDelete(Resource):
    """用户删除订单（仅已完成/已取消）"""
    @deco_catch_view_exception("删除订单")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.delete(user_id, data)


@ns_order.route('/confirm', methods=['POST'])
class OrderConfirm(Resource):
    """用户确认收货（待收货 → 已完成）"""
    @deco_catch_view_exception("确认收货")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.confirm(user_id, data)


@ns_order.route('/remind', methods=['POST'])
class OrderRemind(Resource):
    """用户提醒发货（仅待发货可提醒）"""
    @deco_catch_view_exception("提醒发货")
    def post(self):
        user_id = _get_user_id()
        if not user_id:
            return {"success": False, "message": "请先登录"}
        data = json.loads(request.data)
        return order_service.remind(user_id, data)


# ==================== Admin 端：订单管理 ====================

@ns_order.route('/admin/list', methods=['GET'])
class AdminOrderList(Resource):
    @admin_required
    @deco_catch_view_exception("管理员订单列表")
    def get(self):
        params = {
            'pageNum': int(request.args.get('pageNum', 1)),
            'pageSize': int(request.args.get('pageSize', 10)),
            'orderStatus': request.args.get('status'),
            'orderNo': request.args.get('orderNo', ''),
            'consignee': request.args.get('consignee', ''),
            'phone': request.args.get('phone', ''),
            'payStatus': request.args.get('payStatus'),
        }
        return order_service.admin_list(params)


@ns_order.route('/admin/status-count', methods=['GET'])
class AdminOrderStatusCount(Resource):
    """订单各状态数量统计（含回收站）"""
    @admin_required
    @deco_catch_view_exception("订单状态数量统计")
    def get(self):
        return order_service.admin_status_count()


@ns_order.route('/admin/detail', methods=['GET'])
class AdminOrderDetail(Resource):
    @admin_required
    @deco_catch_view_exception("管理员订单详情")
    def get(self):
        order_no = request.args.get('orderNo', '')
        return order_service.admin_detail(order_no)


@ns_order.route('/admin/print/<orderNo>', methods=['GET'])
class AdminOrderPrint(Resource):
    """获取订单小票打印数据（订单 + 店铺信息）"""
    @admin_required
    @deco_catch_view_exception("订单小票打印数据")
    def get(self, orderNo):
        return order_service.admin_print(orderNo)


@ns_order.route('/admin/process/<orderNo>', methods=['POST'])
class AdminOrderProcess(Resource):
    @admin_required
    @deco_catch_view_exception("管理员处理订单")
    def post(self, orderNo):
        data = json.loads(request.data)
        return order_service.admin_process(orderNo, data)


# ==================== Admin 端：扫码备货记录 ====================

@ns_order.route('/admin/pick/create', methods=['POST'])
class AdminPickCreate(Resource):
    """记录备货完成（同单重复备货拒绝）"""
    @admin_required
    @deco_catch_view_exception("记录备货完成")
    def post(self):
        data = json.loads(request.data)
        data['operatorId'] = request.admin_id or 0
        data['operatorName'] = request.admin_username or ''
        return pick_service.pick_record_create(data)


@ns_order.route('/admin/pick/check', methods=['GET'])
class AdminPickCheck(Resource):
    """查询订单是否已备货"""
    @admin_required
    @deco_catch_view_exception("查询订单备货状态")
    def get(self):
        return pick_service.pick_record_check(request.args.get('orderNo', ''))


@ns_order.route('/admin/pick/list', methods=['GET'])
class AdminPickList(Resource):
    """备货记录列表（分页 + 订单号筛选）"""
    @admin_required
    @deco_catch_view_exception("备货记录列表")
    def get(self):
        return pick_service.pick_record_list(request.args.to_dict())


@ns_order.route('/admin/delete/<orderNo>', methods=['POST'])
class AdminOrderDelete(Resource):
    @admin_required
    @deco_catch_view_exception("管理员删除订单")
    def post(self, orderNo):
        return order_service.admin_delete(orderNo)


@ns_order.route('/admin/recycle/list', methods=['GET'])
class AdminOrderRecycleList(Resource):
    """回收站订单列表"""
    @admin_required
    @deco_catch_view_exception("回收站订单列表")
    def get(self):
        return order_service.admin_recycle_list(request.args.to_dict())


@ns_order.route('/admin/recycle/restore/<orderNo>', methods=['POST'])
class AdminOrderRecycleRestore(Resource):
    """回收站恢复订单"""
    @admin_required
    @deco_catch_view_exception("回收站恢复订单")
    def post(self, orderNo):
        return order_service.admin_recycle_restore(orderNo)


@ns_order.route('/admin/recycle/purge/<orderNo>', methods=['POST'])
class AdminOrderRecyclePurge(Resource):
    """回收站彻底删除订单"""
    @admin_required
    @deco_catch_view_exception("回收站彻底删除订单")
    def post(self, orderNo):
        return order_service.admin_recycle_purge(orderNo)


@ns_order.route('/admin/refund', methods=['POST'])
class AdminOrderRefund(Resource):
    """管理员发起退款"""
    @admin_required
    @deco_catch_view_exception("申请退款")
    def post(self):
        data = json.loads(request.data)
        order_no = data.get('orderNo', '')
        return order_service.admin_refund(order_no, data)
