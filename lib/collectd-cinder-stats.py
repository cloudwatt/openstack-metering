#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing cinder stats
#
# Copyright © 2014 eNovance <licensing@enovance.com>
#
# Authors:
#   Sofer Athlan-Guyot <sofer.athlan@enovance.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Requirments: python-cinderclient, collectd
if __name__ != "__main__":
    import collectd
from cinderclient.client import Client
from datetime import datetime
from time import mktime
from pprint import pformat
from string import find
from functools import partial
from itertools import chain

plugin_name = 'collectd-cinder-stats'
version = '0.1.0'
config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
}

CINDER_SERVICES = (
    "cinder-backup",
    "cinder-scheduler",
    "cinder-volume"
)

STATUSES = {
    'backups': [
        'available',
        'creating',
        'restoring',
        'error',
        'deleting'
    ],
    'snapshots': [
        'creating',
        'available',
        'error'
    ],
    'volumes': [
        'available',
        'error',
        'error_restoring',
        'error_extending',
        'restoring',
        'backing-up',
    ]
}

count = lambda x, y: x + 1
size = lambda x, y: x + y.size
num_attachments = lambda x, y: x + len(y.attachments)
sum_bootable = lambda x, y: x + (getattr(y, 'bootable', 0) in [ 'true', 'True' ])
count_status = lambda status, x, y: x + (y.status == status)

PROPERTIES = {
    'backups': {
        'count' : count,
        'size' : size,
    },
    'snapshots': {
        'count' : count,
        'size' : size,
    },
    'volumes':  {
        'count' : count,
        'size' : size,
        'attached' : num_attachments,
        'bootable' : sum_bootable,
    }
}


class OpenstackUtils:
    def __init__(self, cinder_client):
        self.cinder_client = cinder_client
        self.last_stats = None
        self.connection_done = None
        self.stats = {}

    def get_stats(self):
        volumes = {}
        volume_types = set()
        kwargs = {'search_opts':{'all_tenants': 1}}

        log_verbose("Authenticating to keystone")
        self.cinder_client.authenticate()

        self.stats = { "backups" : {} }
        self.last_stats = int(mktime(datetime.now().timetuple()))

        for volume in self.cinder_client.volumes.list(**kwargs):
            volumes[volume.id] = volume

            # TODO: "None" type are all the volumes before the
            # switch to multi-backend.  Cannot do a thing about
            # them.  Maybe add a DefaultBackend option to the
            # script.  Or Just add the proper property to the
            # volume.
            volume_types.add(getattr(volume, 'volume_type', None))

        # Link the snapshots to their respective backend type
        snapshots = self.cinder_client.volume_snapshots.list(**kwargs)
        for item in snapshots:
            if not volumes.has_key(item.volume_id):
                item.volume_type = None
            else:
                item.volume_type = volumes[item.volume_id].volume_type

        # Link the backup to the fake 'backups' backend type
        backups = self.cinder_client.backups.list()
        for backup in backups:
            backup.volume_type = "backups"

        # Fetch the statistics for volumes, snapshots and backups
        def fetch_stats(kind, hash, items):
            for status in STATUSES[kind]:
                PROPERTIES[kind]["status_" + status] = partial(count_status, status)

            for prop, func in PROPERTIES[kind].items():
                hash[prop] = reduce(func, items, 0)

        fetch_stats("backups", self.stats["backups"], backups)
        for volume_type in volume_types:
            self.stats[volume_type] = { "volumes" : {}, "snapshots" : {} }
            fetch_stats("volumes", self.stats[volume_type]["volumes"],
                        filter(lambda x: x.volume_type == volume_type,
                               volumes.values()))
            fetch_stats("snapshots", self.stats[volume_type]["snapshots"],
                        filter(lambda x: x.volume_type == volume_type,
                               snapshots))

        # Fetch the service states
        services = []
        fetched_services = self.cinder_client.services.list()
        for service in CINDER_SERVICES:
            instances = filter(lambda s: s.binary == service, fetched_services)
            services.append(len(instances))
            services.append(len(filter(lambda s: s.status == "enabled", instances)))
            services.append(len(filter(lambda s: s.state == "up", instances)))

        self.stats["cinder-services"] = services
        return self.stats


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info("%s [verbose]: %s" % (plugin_name, msg))


def log_warning(msg):
    collectd.warning("%s [warning]: %s" % (plugin_name, msg))


def log_error(msg):
    error = "%s [error]: %s\n" % (plugin_name, msg)
    raise(Exception(error))


def dispatch_value(value, plugin_name, date=None, type_name='',
                   type_instance='', plugin_instance='',
                   host=''):
    """Dispatch a value"""
    # host "/" plugin ["-" plugin instance] "/" type ["-" type instance]

    log_verbose('Sending value: %s=%s' %
                (host + '.' + plugin_name + '-' + str(plugin_instance) +
                 '.' + type_name + '-' + type_instance, value))

    val = collectd.Values()
    val.plugin = plugin_name

    if plugin_instance:
        val.plugin_instance = plugin_instance
    if type_name:
        val.type = type_name
    if type_instance:
        val.type_instance = type_instance
    if host:
        val.host = host
    if date:
        val.time = date

    if type(value) == dict:
        for type_inst in value:
            val.type_instance = type_inst
            val.values = [int(value[type_inst])]
            val.dispatch()
    elif type(value) == list:
        val.values = value
        val.dispatch()
    else:
        val.values = [int(value)]
        val.dispatch()


def configure_callback(conf):
    """Receive configuration block"""
    global config
    for node in conf.children:
        if node.key == 'AuthURL':
            config['auth_url'] = node.values[0]
        elif node.key == 'Username':
            config['username'] = node.values[0]
        elif node.key == 'Password':
            config['password'] = node.values[0]
        elif node.key == 'Tenant':
            config['tenant'] = node.values[0]
        elif node.key == 'EndpointType':
            config['endpoint_type'] = node.values[0]
        elif node.key == 'Verbose':
            config['verbose_logging'] = node.values[0]
        else:
            collectd.warning('%s plugin: Unknown config key: %s.'
                             % (plugin_name, node.key))
    if 'auth_url' not in config:
        log_error('AuthURL not defined')

    if 'username' not in config:
        log_error('Username not defined')

    if 'password' not in config:
        log_error('Password not defined')

    if 'tenant' not in config:
        log_error('Tenant not defined')

    log_verbose(
        "Configured with auth_url=%s, username=%s, password=%s, tenant=%s, " %
        (config['auth_url'],
         config['username'],
         config['password'],
         config['tenant']) +
        " endpoint_type=%s" %
        (config['endpoint_type'])
    )


def connect(config):
    # this shouldn't raise any exception as no connection is done when
    # creating the object.  But It may change, so I catch everything.
    try:
        cinder_client = Client('1',
                               username=config['username'],
                               project_id=config['tenant'],
                               api_key=config['password'],
                               auth_url=config['auth_url'],
                               endpoint_type=config['endpoint_type'])
        cinder_client.authenticate()
    except Exception as e:
        log_error("Connection failed: %s" % e)
    return cinder_client


def init_callback():
    """Initialization block"""
    global config
    cinder_client = connect(config)
    log_verbose('Got a valid connection to cinder API')
    config['util'] = OpenstackUtils(cinder_client)


def read_callback(data=None):
    global config
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))

    # plugin instance
    for plugin_instance in info:
        # instance name
        if plugin_instance in ('cinder-services', 'backups'):
            dispatch_value(info[plugin_instance],
                           'cinder',
                           config['util'].last_stats,
                           plugin_instance,
                           '',
                           '',
                           'openstack')
        else:
            for type_name in info[plugin_instance]:
                dispatch_value(info[plugin_instance][type_name],
                               'cinder',
                               config['util'].last_stats,
                               type_name,
                               '',
                               plugin_instance,
                               'openstack')


collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
