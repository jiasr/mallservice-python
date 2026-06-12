from oslo_db import options


def register_opts(conf):
    # 注册 [database] 组选项（connection 等），连接串由 mall.conf 实际配置
    options.set_defaults(conf)
