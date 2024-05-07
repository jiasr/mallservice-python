from oslo_config import cfg


service_opts = [
    cfg.IntOpt('periodic_interval',
               default=1,
               help='Interval, in seconds, between running periodic tasks'),
    cfg.IntOpt('periodic_fuzzy_delay',
               default=1,
               help='Range, in seconds, to randomly delay when starting the'
                    ' periodic task scheduler to reduce stampeding.'
                    ' (Disable by settings to 0)'),
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
