#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing nova hypervisor-stats
#
# Copyright © 2012-2014 eNovance <licensing@enovance.com>
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
# Requirments: python-novaclient, collectd
import collectd

from novaclient.client import Client
from novaclient import exceptions
from datetime import datetime
from time import mktime
from pprint import pformat

class Novautils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None
    
    def get_stats(self):
        self.last_stats = int(mktime(datetime.now().timetuple()))
        return self.nova_client.hypervisors.statistics()._info

# NOTE: This version is grepped from the Makefile, so don't change the
# format of this line.
version = '0.1.0'

config = {
    'endpoint_type': "publicURL",
    'verbose_logging': False,
    'metric_name': 'openstack.nova.hypervisor_stats'
}


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info('nova hypervisor stats plugin [verbose]: %s' % msg)


def dispatch_value(key, value, type, metric_name, date=None, type_instance=None):
    """Dispatch a value"""

    if not type_instance:
        type_instance = key

    value = int(value)
    log_verbose('Sending value: %s=%s' % (type_instance, value))

    val = collectd.Values(plugin=metric_name)
    val.type = type
    if date:
        val.time = date
    val.type_instance = type_instance
    val.values = [value]
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
            config['verbose_logging'] = bool(node.values[0])
        elif node.key == 'MetricName':
            config['metric_name'] = node.values[0]
        else:
            collectd.warning('nova_hypervisor_stats_info plugin: Unknown config key: %s.'
                             % node.key)
    if not config.has_key('auth_url'):
        raise Exception('AuthURL not defined')

    if not config.has_key('username'):
        raise Exception('Username not defined')

    if not config.has_key('password'):
        raise Exception('Password not defined')

    if not config.has_key('tenant'):
        raise Exception('Tenant not defined')

    log_verbose('Configured with auth_url=%s, username=%s, password=%s, tenant=%s, endpoint_type=%s, metric_name=%s' % (config['auth_url'], config['username'], config['password'], config['tenant'], config['endpoint_type'], config['metric_name']))

def init_callback():
    """Initialization block"""
    global config
    nova_client = Client('1.1',
                         username=config['username'],
                         project_id=config['tenant'],
                         api_key=config['password'],
                         auth_url=config['auth_url'],
                         endpoint_type=config['endpoint_type'])
    log_verbose('Got a valid connection to nova API')
    config['util'] = Novautils(nova_client)

def read_callback(data=None):
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for key in info:
        dispatch_value(key, info[key], 'gauge', config['metric_name'], config['util'].last_stats)


plugin_name = 'Collectd-nova-hypervisor-stats.py'

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
