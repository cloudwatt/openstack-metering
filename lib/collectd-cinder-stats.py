#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing nova hypervisor-stats
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

plugin_name = 'collectd-cinder-stats'

# NOTE: This version is grepped from the Makefile, so don't change the
# format of this line.
version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
    'error': None,
    'volume_type': None,
    'metric_name': 'openstack.cinder.stats',
}


class OpenstackUtils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None
        self.connection_done = None
        self.stats = {}

    def _set_stats(self, cinder, meth):
        properties = ['count', 'size', 'status', 'attached', 'bootable']
        for key in properties:
            volume_type = ''
            if find(meth, 'snapshots') >= 0:
                if key in ['attached', 'bootable']:
                    continue
            if hasattr(cinder, 'volume_type'):
                # TODO: "None" type are all the volumes before the
                # switch to multi-backend.  Cannot do a thing about
                # them.  Maybe add a DefaultBackend option to the
                # script.  Or Just add the proper property to the
                # volume.

                volume_type = cinder.volume_type
            else:
                volume_type = None

            if volume_type not in self.stats:
                self.stats[volume_type] = {meth: {}}

            if find(key, 'status') >= 0:
                key = 'status_' + cinder.status

            if key not in self.stats[volume_type][meth]:
                self.stats[volume_type][meth][key] = 0

            if find(key, 'size') >= 0:
                self.stats[volume_type][meth][key] += cinder.size
            elif find(key, 'attached') >= 0:
                self.stats[volume_type][meth][key] += len(cinder.attachments)
            elif find(key, 'boot') >= 0:
                if cinder.bootable and \
                   cinder.bootable not in ['false', 'False']:
                    self.stats[volume_type][meth][key] += 1
            else:
                self.stats[volume_type][meth][key] += 1

    def get_stats(self, volume_type):
        self.stats = {}
        self.last_stats = int(mktime(datetime.now().timetuple()))
        informations = {'volumes': self.nova_client.volumes.list,
                        'snapshots': self.nova_client.volume_snapshots.list}
        for meth in informations:
            # this seems to be one connection per tenant.
            data = informations[meth](search_opts={'all_tenants': 1})
            number_data = len(data)
            counter = 0
            while counter < number_data:
                # try to keep memory usage minimal
                v = data.pop()
                counter += 1
                self._set_stats(v, meth)

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
        elif node.key == 'MetricName':
            config['metric_name'] = node.values[0]
        elif node.key == 'VolumeType':
            config['volume_type'] = node.values[0]
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
        " endpoint_type=%s, metric_name=%s" %
        (config['endpoint_type'],
         config['metric_name'])
    )


def connect(config):
    # this shouldn't raise any exception as no connection is done when
    # creating the object.  But It may change, so I catch everything.
    try:
        nova_client = Client('1',
                             username=config['username'],
                             project_id=config['tenant'],
                             api_key=config['password'],
                             auth_url=config['auth_url'],
                             endpoint_type=config['endpoint_type'])
        nova_client.authenticate()
    except Exception as e:
        log_error("Connection failed: %s" % e)
    return nova_client


def init_callback():
    """Initialization block"""
    global config
    nova_client = connect(config)
    log_verbose('Got a valid connection to cinder API')
    config['util'] = OpenstackUtils(nova_client)


def read_callback(data=None):
    global config
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats(config['volume_type'])
    log_verbose(pformat(info))
    # plugin instance
    for plugin_instance in info:
        # instance name
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
