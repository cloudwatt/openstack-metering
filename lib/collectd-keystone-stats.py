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
# Requirements:  python-keystoneclient, collectd
if __name__ != "__main__":
    import collectd
from keystoneclient.v2_0 import client
from datetime import datetime
from time import mktime
from pprint import pformat
from string import find

plugin_name = 'collectd-keystone-stats'

version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
}


class OpenstackUtils:
    def __init__(self, keystone_client):
        self.keystone_client = keystone_client
        self.last_stats = None
        self.connection_done = None
        self.stats = {}

    def get_stats(self):
        stats = {}
        self.last_stats = int(mktime(datetime.now().timetuple()))
        log_verbose("Authenticating to keystone")
        self.keystone_client.authenticate()
        users = self.keystone_client.users.list()
        count = len(users)
        enabled = reduce(lambda x, y: x + int(y.enabled), users, 0)
        stats['users'] = [ count, enabled, count - enabled ]
        stats['tenants'] = len(self.keystone_client.tenants.list())
        return stats


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info("%s [verbose]: %s\n" % (plugin_name, msg))


def log_warning(msg):
    collectd.warning("%s [warning]: %s\n" % (plugin_name, msg))


def log_error(msg):
    error = "%s [error]: %s\n" % (plugin_name, msg)
    raise(Exception(error))


def dispatch_value(key, value, type_name, plugin_name, date=None,
                   type_instance='', plugin_instance='',
                   host=''):
    """Dispatch a value"""

    value = int(value)
    log_verbose('Sending value: %s=%s' %
                (host + '.' + plugin_name + '-' + plugin_instance +
                 '.' + type_name + '-' + type_instance, value))

    val = collectd.Values()
    val.plugin = plugin_name
    val.type = type_name
    val.values = [value]

    if plugin_instance:
        val.plugin_instance = plugin_instance
    if type_instance:
        val.type_instance = type_instance
    if host:
        val.host = host
    if date:
        val.time = date

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
    try:
        keystone_client = client.Client(
            username=config['username'],
            tenant_name=config['tenant'],
            password=config['password'],
            auth_url=config['auth_url'],
        )
        keystone_client.authenticate()
        if not keystone_client.tenants.list():
            log_error("The user must have the admin role.")
    except Exception as e:
        log_error("Connection failed: %s" % e)
    return keystone_client


def init_callback():
    """Initialization block"""
    global config
    client = connect(config)
    config['util'] = OpenstackUtils(client)
    log_verbose('Got a valid connection to keystone API')


def _naming(key, info):
    global config
    names = {
        'plugin_name': '',
        'plugin_instance': '',
        'type_name': '',
        'type_instance': ''
    }
    if find(key, 'users') >= 0:
        names['type_name'] = 'accounts'
    else:
        names['type_name'] = 'tenants'
    return names


def read_callback(data=None):
    global config
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for key in info:
        names = _naming(key, info)
        dispatch_value(key,
                       info[key],
                       names['type_name'],
                       'keystone',
                       config['util'].last_stats,
                       '',
                       '',
                       'openstack')

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
