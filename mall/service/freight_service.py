"""运费模板业务逻辑层"""
from mall.db.models.Freight.sql import FreightTemplateDao, FreightRegionDao


def template_list(params):
    return FreightTemplateDao.list(
        int(params.get('pageNum', 1)),
        int(params.get('pageSize', 20)),
    )


def template_detail(template_id):
    return FreightTemplateDao.detail(template_id)


def template_create(data):
    return FreightTemplateDao.create(data)


def template_update(template_id, data):
    return FreightTemplateDao.update(template_id, data)


def template_delete(template_id):
    return FreightTemplateDao.delete(template_id)


def template_set_default(template_id):
    return FreightTemplateDao.set_default(template_id)


def region_list(template_id):
    return FreightRegionDao.list(template_id)


def region_save(template_id, data):
    return FreightRegionDao.save(template_id, data.get('regions', []))
