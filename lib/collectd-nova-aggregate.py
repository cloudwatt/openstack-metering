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
from datetime import datetime
from time import mktime
from pprint import pformat
from novaclient import exceptions


class Novautils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None
        self.hypervisors = None

    def get_stats(self):
        stats = {}
        self.hypervisors = None
        self.last_stats = int(mktime(datetime.now().timetuple()))
        hosts_by_aggregate = self._hosts_by_aggregate()
        for aggregate, hosts in hosts_by_aggregate.items():
            stats[aggregate] = dict.fromkeys(['vcpus', 'vcpus_used', 'memory_mb', 'memory_mb_used', 'local_gb', 'local_gb_used', 'disk_available_least', 'running_vms'], 0)
            for host in hosts:
                stats[aggregate] = {
                    'vcpus': stats[aggregate]['vcpus'] + host.vcpus,
                    'vcpus_used': stats[aggregate]['vcpus_used'] + host.vcpus_used,
                    'memory_mb': stats[aggregate]['memory_mb'] + host.memory_mb,
                    'memory_mb_used': stats[aggregate]['memory_mb_used'] + host.memory_mb_used,
                    'local_gb': stats[aggregate]['local_gb'] + host.local_gb,
                    'local_gb_used': stats[aggregate]['local_gb_used'] + host.local_gb_used,
                    'disk_available_least': stats[aggregate]['disk_available_least'] + host.disk_available_least,
                    'running_vms': stats[aggregate]['running_vms'] + host.running_vms
                }
        return stats

    def _hosts_by_aggregate(self):
        hba = {}
        for aggregate in self.nova_client.aggregates.list():
            hba[aggregate.name] = []
            for hypervisor in aggregate.hosts:
                try:
                    hba[aggregate.name].append(self._search_hypervisor_by_name(aggregate.name))
                except exceptions.NotFound as e:
                    log_warning("Cannot find %s hypervisor: %s" %
                                (hypervisor, e))
                except Exception as e:
                    log_error("Problem retrieving hypervisor: %s" % e)
        return hba

    def _search_hypervisor_by_name(self, name):
        """ Replace search to minimize the number of calls. """
        if not self.hypervisors:
            self.hypervisors = {}
            hypervisors = self.nova_client.hypervisors.list()
            for hypervisor in hypervisors:
                self.hypervisors[hypervisor.service['host']] = hypervisor
        if name in self.hypervisors:
            return self.hypervisors[name]
        else:
            raise exceptions.NotFound


# NOTE: This version is grepped from the Makefile, so don't change the
# format of this line.
version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
    'error': None,
    'metric_name': 'openstack.nova.aggregates'
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


def dispatch_value(key, value, type, metric_name, date=None,
                   type_instance=None):
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
            config['verbose_logging'] = node.values[0]
        elif node.key == 'MetricName':
            config['metric_name'] = node.values[0]
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
    config['util'] = Novautils(nova_client)


def read_callback(data=None):
    global config
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for aggregate in info:
        for key in info[aggregate]:
            dispatch_value(key,
                           info[aggregate][key],
                           'gauge',
                           config['metric_name'] + '.' + aggregate,
                           config['util'].last_stats)


plugin_name = 'collectd-nova-aggregate'

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
