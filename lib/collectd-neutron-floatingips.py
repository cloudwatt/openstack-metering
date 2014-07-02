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
# Requirments: python-neutronclient, python-keystoneclient, collectd
import collectd

from keystoneclient.v2_0 import client
from neutronclient.neutron import client as neutron
from datetime import datetime
from time import mktime
from pprint import pformat
import re

plugin_name = 'collectd-neutron-floatingips'


class Novautils:
    def __init__(self, neutron_client, public_network=None):
        self.neutron_client = neutron_client
        self.last_stats = None
        self.connection_done = None
        self.public_network = public_network

    def check_connection(self, force=False):
        if not self.connection_done or force:
            try:
                # force a connection to the server
                self.connection_done = self.neutron_client.list_ports()
            except Exception as e:
                log_error("Cannot connect to neutron: %s\n" % e)

    def get_stats(self):
        stats = {}
        self.last_stats = int(mktime(datetime.now().timetuple()))
        stats['used'] = len(self.neutron_client.list_floatingips(
            fields='tenant_id')['floatingips'])
        if self.public_network:
            total_ip = self._estimate_total_ip()
            if total_ip:
                stats['total_ips_estimate'] = total_ip

        return stats

    def _estimate_total_ip(self):
        total_ip = 0
        subnet_mask = re.compile('[^/]+/(\d{1,2})')
        subnets_from_public_network = []
        try:
            subnets_from_public_network = self.neutron_client.list_networks(
                name=self.public_network)['networks'][0]['subnets']
        except Exception as e:
            log_warning("Cannot get subnets associated with %s network: %s" %
                        (self.public_network, e))
            return None

        for public_subnet_id in subnets_from_public_network:
            net_info = self.neutron_client.list_subnets(
                id=public_subnet_id,
                fields=['cidr', 'gateway_ip'])['subnets'][0]
            subnet_match = subnet_mask.match(net_info['cidr'])
            if not subnet_match:
                log_warning("Cannot retrieve the subnet mask of subnet_id %" %
                            public_subnet_id)
                next
            subnet = int(subnet_match.group(1))
            ips_number = 2**(32 - subnet)
            if 'gateway_ip' in net_info and net_info['gateway_ip']:
                ips_number -= 1
            ips_number -= 2
            total_ip += ips_number
        return total_ip

# NOTE: This version is grepped from the Makefile, so don't change the
# format of this line.
version = '0.1.0'

config = {
    'endpoint_type': "publicURL",
    'verbose_logging': False,
    'public_network': 'public',
    'error': None,
    'metric_name': 'openstack.neutron.floating_ips',
}


def log_verbose(msg):
    if not config['verbose_logging']:
        return
    collectd.info("%s [verbose]: %s" % (plugin_name, msg))


def log_warning(msg):
    collectd.warning("%s [warning]: %s" % (plugin_name, msg))


def log_error(msg):
    global config
    error = "%s [error]: %s" % (plugin_name, msg)
    collectd.error(error)
    config['error'] = error


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
            config['verbose_logging'] = bool(node.values[0])
        elif node.key == 'MetricName':
            config['metric_name'] = node.values[0]
        elif node.key == 'PublicNetwork':
            config['public_network'] = node.values[0]
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
         config['metric_name']) +
        " public_network=%s" % config['public_network']
    )


def connect(config):
    try:
        nova_client = client.Client(
            username=config['username'],
            tenant_name=config['tenant'],
            password=config['password'],
            auth_url=config['auth_url'],
        )
        nova_client.authenticate()
        if not nova_client.tenants.list():
            log_error("The user must have the admin role to work.")
    except Exception as e:
        log_error("Authentication error: %s\n" % e)
    endpoint = nova_client.service_catalog.get_endpoints(
        'network')['network'][0][config['endpoint_type']]
    token = nova_client.service_catalog.get_token()['id']
    neutron_client = neutron.Client('2.0',
                                    endpoint_url=endpoint,
                                    token=token)
    conf = {'neutron_client': neutron_client}
    if config['public_network'] and config['public_network'] != 'none':
        conf['public_network'] = config['public_network']
    config['util'] = Novautils(**conf)
    config['util'].check_connection()


def init_callback():
    """Initialization block"""
    global config
    connect(config)
    log_verbose('Got a valid connection to nova API')


def read_callback(data=None):
    if config['error']:
        log_warning("Got a error during initialization.  " +
                    "Fix it and restart collectd")
        return
    if 'util' not in config:
        if not config['util'].connection_done:
            log_warning("Connection has not been done. Exiting.")
            return
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for key in info:
        dispatch_value(key,
                       info[key],
                       'gauge',
                       config['metric_name'],
                       config['util'].last_stats)

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
