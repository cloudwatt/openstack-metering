#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing nova hypervisor-stats
#
# Copyright © 2014 eNovance <licensing@enovance.com>
#
# Authors:
#   Sylvain Baubeau <sylvain.baubeau@enovance.com>
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

from ceilometerclient.client import get_client

from datetime import datetime
from time import mktime
from pprint import pformat
from string import find

plugin_name = 'collectd-ceilometer-stats'

version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
}


class OpenstackUtils:
    def __init__(self, client):
        self.client = client
        self.last_stats = None
        self.connection_done = None
        self.stats = {}

    def get_stats(self):
        alarms = self.client.alarms.list()
        self.last_stats = int(mktime(datetime.now().timetuple()))
        self.stats = {'alarms': {
                          'ok': len(filter(lambda x: x.state == 'ok', alarms)),
                          'alarm': len(filter(lambda x: x.state == 'alarm', alarms)),
                          'insufficient_data': len(filter(lambda x: x.state == 'insufficient data', alarms))
                      }, 
                      'meters': len(self.client.meters.list())}
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

    log_verbose('Dispatch value:\nhost: %s\nplugin_name: %s\n'
                'plugin_instance: %s\ntype_name: %s\n'
                'type_instance: %s\nvalue: %s\n' %
                (host, plugin_name, str(plugin_instance),
                 type_name, type_instance, value))

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
        client = get_client('2',
                            os_username=config['username'],
                            os_tenant_name=config['tenant'],
                            os_password=config['password'],
                            os_auth_url=config['auth_url'],
                            os_endpoint_type=config['endpoint_type'])
    except Exception as e:
        log_error("Connection failed: %s" % e)
    return client


def init_callback():
    """Initialization block"""
    ceilometer_client = connect(config)
    log_verbose('Got a valid connection to ceilometer API')
    config['util'] = OpenstackUtils(ceilometer_client)


def read_callback(data=None):
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    # plugin instance
    for plugin_instance in info:
        # instance name
        for type_name in info[plugin_instance]:
            dispatch_value(info[plugin_instance][type_name],
                           'ceilometer',
                           config['util'].last_stats,
                           type_name,
                           '',
                           plugin_instance,
                           'openstack')


collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)

