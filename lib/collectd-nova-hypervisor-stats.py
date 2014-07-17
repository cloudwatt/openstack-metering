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
# Requirments: python-novaclient, collectd
if __name__ != "__main__":
    import collectd
from novaclient.client import Client
from datetime import datetime
from time import mktime
from pprint import pformat


class OpenstackUtils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None

    def get_stats(self):
        self.last_stats = int(mktime(datetime.now().timetuple()))
        data = self.nova_client.hypervisors.statistics()._info
        vcpu_multiplier = 1
        memory_multiplier = 1
        if 'overcommit' in config and aggregate in config['overcommit']:
                vcpu_multiplier = config['overcommit']['vcpus']
                memory_multiplier = config['overcommit']['memory']

        return {
            'servers': [data['count'], data['current_workload']],
            'disk': [data['local_gb'], data['local_gb_used'],
                     data['free_disk_gb'], data['disk_available_least']],
            'memory': {'total': data['memory_mb'],
                       'used': data['memory_mb_used'],
                       'free': data['free_ram_mb']},
            'instances': [data['running_vms']],
            'vcpus': {
                'total': data['vcpus'],
                'used': data['vcpus_used'],
                'real': data['vcpus']
            }}

version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
    'error': None,
}


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info("%s [verbose]: %s\n" % (plugin_name, msg))


def log_warning(msg):
    collectd.warning("%s [warning]: %s" % (plugin_name, msg))


def log_error(msg):
    error = "%s [error]: %s\n" % (plugin_name, msg)
    raise(Exception(error))


def dispatch_value(value, plugin_name, date=None, type_name='',
                   type_instance='', plugin_instance='',
                   host=''):
    """Dispatch a value"""

    log_verbose('Sending value: %s=%s' %
                (host + '.' + plugin_name + '-' + plugin_instance +
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
        val.values = int(value)
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
        elif node.key == 'Overcommit':
            for nd in node.children:
                if type(nd.values[0]) != float:
                    log_error("You must pass a float to Vcpus,Memory")
                if nd.key == 'Vcpus':
                    config['overcommit']['vcpus'] = nd.values[0]
                elif nd.key == 'Memory':
                    config['overcommit']['memory'] = nd.values[0]
                else:
                    collectd.warning('%s plugin: Unknown subconfig key for Overcommit: %s'
                                     % (plugin_name, nd.key))
            for required_param in ['vcpus', 'memory']:
                if required_param not in config['overcommit']:
                    log_error('%s not defined in %s'
                              % (required_param, aggregate))
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
    nova_client = Client('1.1',
                         username=config['username'],
                         project_id=config['tenant'],
                         api_key=config['password'],
                         auth_url=config['auth_url'],
                         endpoint_type=config['endpoint_type'])
    try:
        nova_client.authenticate()
    except Exception as e:
        log_error("Connection failed: %s" % e)
    return nova_client


def init_callback():
    """Initialization block"""
    global config
    nova_client = connect(config)
    log_verbose('Got a valid connection to nova API')
    config['util'] = OpenstackUtils(nova_client)


def read_callback(data=None):
    global config
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for key in info:
        dispatch_value(info[key],
                       'hypervisors',
                       config['util'].last_stats,
                       key,
                       '',
                       '',
                       'openstack')


plugin_name = 'collectd-nova-hypervisor-stats'

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
