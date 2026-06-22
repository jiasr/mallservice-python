"""运费模板 API 路由"""
import json
from flask import Blueprint, request
from flask_restx import Namespace, Resource

from mall.common.common import deco_catch_view_exception, admin_required
from mall.service import freight_service

app_freight = Blueprint('freight', __name__)
ns_freight = Namespace("freight", description="运费模板管理", path="/v1/order/admin/freight")


@ns_freight.route('/template/list', methods=['GET'])
class FreightTemplateList(Resource):
    @admin_required
    @deco_catch_view_exception("运费模板列表")
    def get(self):
        params = {
            'pageNum': request.args.get('pageNum', 1),
            'pageSize': request.args.get('pageSize', 20),
        }
        return freight_service.template_list(params)


@ns_freight.route('/template/detail', methods=['GET'])
class FreightTemplateDetail(Resource):
    @admin_required
    @deco_catch_view_exception("运费模板详情")
    def get(self):
        template_id = int(request.args.get('id', 0))
        return freight_service.template_detail(template_id)


@ns_freight.route('/template/add', methods=['POST'])
class FreightTemplateAdd(Resource):
    @admin_required
    @deco_catch_view_exception("新增模板")
    def post(self):
        data = json.loads(request.data)
        return freight_service.template_create(data)


@ns_freight.route('/template/update/<int:template_id>', methods=['POST'])
class FreightTemplateUpdate(Resource):
    @admin_required
    @deco_catch_view_exception("更新模板")
    def post(self, template_id):
        data = json.loads(request.data)
        return freight_service.template_update(template_id, data)


@ns_freight.route('/template/delete/<int:template_id>', methods=['POST'])
class FreightTemplateDelete(Resource):
    @admin_required
    @deco_catch_view_exception("删除模板")
    def post(self, template_id):
        return freight_service.template_delete(template_id)


@ns_freight.route('/template/set-default/<int:template_id>', methods=['POST'])
class FreightTemplateSetDefault(Resource):
    @admin_required
    @deco_catch_view_exception("设为默认模板")
    def post(self, template_id):
        return freight_service.template_set_default(template_id)


@ns_freight.route('/region/list', methods=['GET'])
class FreightRegionList(Resource):
    @admin_required
    @deco_catch_view_exception("地区规则列表")
    def get(self):
        template_id = int(request.args.get('templateId', 0))
        return freight_service.region_list(template_id)


@ns_freight.route('/region/save', methods=['POST'])
class FreightRegionSave(Resource):
    @admin_required
    @deco_catch_view_exception("保存地区规则")
    def post(self):
        data = json.loads(request.data)
        template_id = int(data.get('templateId', 0))
        return freight_service.region_save(template_id, data)
