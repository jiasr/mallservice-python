"""用户协议与隐私政策 API 路由"""
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource
from oslo_log import log as logging

from mall.service import agreement_service
from mall.common.common import admin_required

LOG = logging.getLogger(__name__)

app_agreement = Blueprint('agreement', __name__)
ns_agreement = Namespace("agreement", description="用户协议与隐私政策接口", path="/v1/agreement")
ns_agreement_admin = Namespace("agreement-admin", description="用户协议管理接口", path="/v1/admin/agreement")


# ==================== 小程序端：获取协议内容 ====================
@ns_agreement.route('/get', methods=['GET'])
class AgreementGet(Resource):
    """获取指定类型的协议（type=agreement 用户协议 / privacy 隐私政策）"""
    def get(self):
        agreement_type = request.args.get('type', 'agreement').strip()
        return agreement_service.agreement_get(agreement_type)


# ==================== 管理端：后台可配置 ====================
@ns_agreement_admin.route('/list', methods=['GET'])
class AgreementAdminList(Resource):
    """后台配置：分页查询所有协议"""
    @admin_required
    def get(self):
        params = request.args.to_dict()
        return agreement_service.agreement_list(params)


@ns_agreement_admin.route('/save', methods=['POST'])
class AgreementAdminSave(Resource):
    """后台配置：新增或更新协议"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return agreement_service.agreement_save(data)


@ns_agreement_admin.route('/delete', methods=['POST'])
class AgreementAdminDelete(Resource):
    """后台配置：删除协议"""
    @admin_required
    def post(self):
        data = json.loads(request.data)
        return agreement_service.agreement_delete(data.get('id'))
