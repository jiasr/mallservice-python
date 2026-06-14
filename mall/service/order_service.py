"""订单业务层"""
from mall.db.models.Order.sql import OrderDao


def preview(user_id, data):
    return OrderDao.preview(user_id, data.get('items', []))


def create(user_id, data):
    return OrderDao.create(user_id, data)


def detail(user_id, order_id):
    return OrderDao.get_detail(order_id, user_id)


def cancel(user_id, data):
    return OrderDao.cancel(data.get('orderId', ''), user_id)
