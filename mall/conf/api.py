from oslo_config import cfg


service_opts = [
    cfg.StrOpt('api_mall_listen',
               default="0.0.0.0",
               help='IP address on which OpenStack Venus API listens'),
    cfg.IntOpt('api_mall_listen_port',
               default=8560,
               min=1, max=65535,
               help='Port on which OpenStack Venus API listens'),
    cfg.IntOpt('api_mall_workers',
               help='Number of workers for OpenStack Venus API service. '
                    'The default is equal to the number of CPUs available.'), ]


def register_opts(conf):
    conf.register_opts(service_opts)
