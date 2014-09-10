#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd plugin for graphing Nova stats
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
# Requirements: python-novaclient, collectd
if __name__ != "__main__":
    import collectd

from novaclient.client import Client
from datetime import datetime
from time import mktime
from pprint import pformat
from novaclient import exceptions


plugin_name = 'collectd-nova-stats'
version = '0.1.0'
config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
}

NOVA_SERVICES = (
    "nova-cert",
    "nova-compute",
    "nova-conductor",
    "nova-consoleauth",
    "nova-scheduler"
)


class OpenstackUtils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None
        self.hypervisors = None

    def get_stats(self):
        aggregates = {}
        self.hypervisors = None
        self.last_stats = int(mktime(datetime.now().timetuple()))
        log_verbose("Authenticating to keystone")
        self.nova_client.authenticate()
        hosts_by_aggregate = self._hosts_by_aggregate()
        for aggregate, hosts in hosts_by_aggregate.items():
            vcpu_multiplier = 1
            memory_multiplier = 1
            if 'overcommit' in config and aggregate in config['overcommit']:
                vcpu_multiplier = config['overcommit'][aggregate]['vcpus']
                memory_multiplier = config['overcommit'][aggregate]['memory']
            aggregates[aggregate] = {
                'disk': [0, 0, 0, 0],
                'vcpus': dict.fromkeys(['total',
                                        'used',
                                        'real'], 0),
                'instances': 0,
                'memory': dict.fromkeys(['total',
                                         'used',
                                         'free'], 0),
                'servers': [len(hosts), 0]
            }
            for host in hosts:
                aggregates[aggregate] = {
                    'instances': aggregates[aggregate]['instances'] + host.running_vms,
                    'disk': [x[0] + x[1] for x in zip(
                        aggregates[aggregate]['disk'], [
                            host.local_gb,
                            host.local_gb_used,
                            host.free_disk_gb,
                            host.disk_available_least,
                        ]
                    )],
                    'memory': {
                        'total': aggregates[aggregate]['memory']['total'] + host.memory_mb * memory_multiplier,
                        'real': aggregates[aggregate]['memory']['total'] + host.memory_mb,
                        'used': (aggregates[aggregate]['memory']['total']
                                 + host.memory_mb * memory_multiplier
                                 - aggregates[aggregate]['memory']['used']
                                 + host.memory_mb_used),
                        'used_real':  aggregates[aggregate]['memory']['used'] + host.memory_mb_used,
                        'free':  aggregates[aggregate]['memory']['free'] + host.free_ram_mb,
                    },
                    'vcpus': {
                        'total': aggregates[aggregate]['vcpus']['total'] + host.vcpus * vcpu_multiplier,
                        'real': aggregates[aggregate]['vcpus']['real'] + host.vcpus,
                        'used': aggregates[aggregate]['vcpus']['used'] + host.vcpus_used,
                    },
                    'servers': [x[0] + x[1] for x in zip(
                        aggregates[aggregate]['servers'],
                        [0, host.current_workload])]
                }

            if aggregates[aggregate]['servers'][0] > 0:
                aggregates[aggregate]['servers'][1] = \
                    aggregates[aggregate]['servers'][1] // \
                    aggregates[aggregate]['servers'][0]

        services = []
        fetched_services = self.nova_client.services.list()
        for service in NOVA_SERVICES:
            instances = filter(lambda s: s.binary == service, fetched_services)
            services.append(len(instances))
            services.append(len(filter(lambda s: s.state == "up", instances)))
            services.append(len(filter(lambda s: s.status == "enabled", instances)))

        return { 'aggregates' : aggregates,
                 'nova-services' : services }

    def _hosts_by_aggregate(self):
        hba = {}
        for aggregate in self.nova_client.aggregates.list():
            hba[aggregate.name] = []
            for hypervisor in aggregate.hosts:
                try:
                    hba[aggregate.name].append(self._search_hypervisor_by_name(hypervisor))
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
            raise(exceptions.NotFound("'%s' is not on hypervisors list" % name))


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
        elif node.key == 'Overcommit':
            for aggregate in node.values:
                config['overcommit'] = {aggregate: {}}
                for nd in node.children:
                    if type(nd.values[0]) != float:
                        log_error("You must pass a float to %s" % aggregate + '-vcpus,memory')
                    if nd.key == 'Vcpus':
                        config['overcommit'][aggregate]['vcpus'] = nd.values[0]
                    elif nd.key == 'Memory':
                        config['overcommit'][aggregate]['memory'] = nd.values[0]
                    else:
                        collectd.warning(
                            '%s plugin: Unknown subconfig key for Overcommit: %s'
                            % (plugin_name, nd.key))
                for required_param in ['vcpus', 'memory']:
                    if required_param not in config['overcommit'][aggregate]:
                        log_error('%s not defined in %s'
                                  % (required_param, aggregate))
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
    nova_client = connect(config)
    log_verbose('Got a valid connection to nova API')
    config['util'] = OpenstackUtils(nova_client)


def read_callback(data=None):
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for aggregate in info['aggregates']:
        for key in info['aggregates'][aggregate]:
            dispatch_value(info['aggregates'][aggregate][key],
                           'hypervisors',
                           config['util'].last_stats,
                           key,
                           '',
                           aggregate,
                           'openstack')

    dispatch_value(info['nova-services'],
                   'nova',
                    config['util'].last_stats,
                    'nova-services',
                    '',
                    '',
                    'openstack')


collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
