# -*- encoding : utf-8 -*-
import json

from flask import Blueprint, request
from flask_restx import Namespace, Resource, fields
from oslo_log import log as logging


LOG = logging.getLogger(__name__)

app_admin = Blueprint('admin', __name__)
ns_admin = Namespace("admin", description="admin ", path="/v1/admin")



@ns_admin.route('/login', methods=['POST'])
class AdminLogin(Resource):

    def post(self):
        data = json.loads(request.data)
        LOG.info(data)
        return {
                  "flag": True,
                  "resData": {
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                  }
                }

@ns_admin.route('/getinfo', methods=['POST'])
class AdminLogin(Resource):

    def post(self):
        # data = json.loads(request.data)
        # LOG.info(data)
        return {
  "flag": True,
  "resData": {
    "username": "admin",
    "avatar": "https://example.com/avatar.png",
    "menus": [
      {
        "name": "商品管理",
        "frontpath": "/goods/list",
        "icon": "Goods",
        "child": [
          {
            "name": "商品列表",
            "frontpath": "/goods/list",
            "icon": "List"
          },
          {
            "name": "添加商品",
            "frontpath": "/goods/add",
            "icon": "Plus"
          }
        ]
      },
      {
        "name": "分类管理",
        "frontpath": "/category/list",
        "icon": "Menu"
      }
    ],
    "ruleNames": ["user:list", "goods:add"]
  }
}