"""购物车业务层"""
from mall.db.models.Cart.sql import CartDao


def get_cart(user_id):
    return CartDao.get_user_cart(user_id)


def add_to_cart(user_id, data):
    return CartDao.add_to_cart(
        user_id,
        data.get('spuId', ''),
        data.get('skuId', ''),
        int(data.get('quantity', 1))
    )


def update_cart(user_id, data):
    return CartDao.update_cart(user_id, data)


def delete_cart(user_id, data):
    return CartDao.delete_cart(user_id, data)


def clear_cart(user_id):
    return CartDao.clear_cart(user_id)
