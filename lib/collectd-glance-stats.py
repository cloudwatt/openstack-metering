#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing Glance image stats
#
# Copyright © 2014 eNovance <licensing@enovance.com>
#
# Authors:
#   Sofer Athlan-Guyot <sofer.athlan@enovance.com>
#   Sylvain Baubeau <sylvain.baubeau@enovance.com>
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
# Requirments: python-neutronclient, python-keystoneclient, collectd
if __name__ != "__main__":
    import collectd
import glanceclient.client as glance
from keystoneclient.v2_0 import client as keystone
from datetime import datetime
from time import mktime
from pprint import pformat
import re


plugin_name = 'collectd-glance-stats'
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

    def get_stats(self):
        stats = {}
        self.last_stats = int(mktime(datetime.now().timetuple()))
        # This is not very smart as we could just fetch all the images
        # and filter on the client...
        stats['public'] = len(list(self.client.images.list(
            filters={'visibility': 'public', 'member_status': 'all'})))
        stats['private'] = len(list(self.client.images.list(
            filters={'visibility': 'private', 'member_status': 'all'})))
        stats['shared'] = len(list(self.client.images.list(
            filters={'visibility': 'shared', 'member_status': 'all'})))

        return stats


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info("%s [verbose]: %s" % (plugin_name, msg))


def log_warning(msg):
    collectd.warning("%s [warning]: %s" % (plugin_name, msg))


def log_error(msg):
    error = "%s [error]: %s" % (plugin_name, msg)
    raise(Exception(error))


def dispatch_value(value, type_name, plugin_name, date=None,
                   type_instance=None, plugin_instance=None,
                   host=None):
    """Dispatch a value"""

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
            config['verbose_logging'] = bool(node.values[0])
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
        "Configured with auth_url=%s, username=%s, " \
        "password=%s, tenant=%s, endpoint_type=%s" %
        (config['auth_url'],
         config['username'],
         config['password'],
         config['tenant'],
         config['endpoint_type'])
    )


def connect(config):
    # The Glance client is not able to query Keystone
    # for the endpoint, neither authenticate itself
    ksclient = keystone.Client(username=config['username'],
                               tenant_name=config['tenant'],
                               password=config['password'],
                               auth_url=config['auth_url'])

    endpoint = ksclient.service_catalog.url_for(
                   service_type='image',
                   endpoint_type=config['endpoint_type']
               )

    # Strip version from the last component of endpoint if present
    # Get rid of trailing '/' if present
    if endpoint.endswith('/'):
        endpoint = endpoint[:-1]
    url_bits = endpoint.split('/')
    # regex to match 'v1' or 'v2.0' etc
    if re.match('v\d+\.?\d*', url_bits[-1]):
        endpoint = '/'.join(url_bits[:-1])

    client = glance.Client('2',
                           endpoint=endpoint,
                           token=ksclient.auth_token)

    config['util'] = OpenstackUtils(client)


def init_callback():
    """Initialization block"""
    connect(config)
    log_verbose('Got a valid connection to glance API')


def read_callback(data=None):
    connect(config)

    try:
        info = config['util'].get_stats()
        log_verbose(pformat(info))
        for key, value in info.items():
            dispatch_value(value,
                           key,
                           'glance',
                           config['util'].last_stats,
                           '',
                           '',
                           'openstack')
    except Exception as e:
        log_warning(
            "Problem while reading, trying to authenticate (%s)" % e)
        log_warning("Trying to reconnect (%s)" % e)
        connect(config)


collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
