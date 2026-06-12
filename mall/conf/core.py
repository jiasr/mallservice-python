from oslo_config import cfg


core_opts = [
    cfg.StrOpt('state_path',
               default='/var/lib/mall',
               deprecated_name='pybasedir',
               help="Top-level directory for "
                    "maintaining mall's state"),
]


def register_opts(conf):
    conf.register_cli_opts(core_opts)
