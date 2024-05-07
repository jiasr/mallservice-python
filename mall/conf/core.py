from oslo_config import cfg


core_opts = [
    cfg.StrOpt('api_paste_config',
               default="api-paste.ini",
               help='File name for the paste.'
                    'deploy config for venus-api'),
    cfg.StrOpt('state_path',
               default='/var/lib/mall',
               deprecated_name='pybasedir',
               help="Top-level directory for "
                    "maintaining venus's state"),
]


def register_opts(conf):
    conf.register_cli_opts(core_opts)
