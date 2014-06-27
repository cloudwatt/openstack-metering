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
# Requirments: python-cinderclient, collectd
import collectd
from cinderclient.client import Client
from datetime import datetime
from time import mktime
from pprint import pformat
from string import find

plugin_name = 'collectd-volumes-stats'

# NOTE: This version is grepped from the Makefile, so don't change the
# format of this line.
version = '0.1.0'

config = {
    'endpoint_type': "publicURL",
    'verbose_logging': False,
    'error': None,
    'volume_type': None,
    'metric_name': 'openstack.cinder.stats',
}


class Novautils:
    def __init__(self, nova_client):
        self.nova_client = nova_client
        self.last_stats = None
        self.connection_done = None
        self.stats = {}

    def check_connection(self, force=False):
        if not self.connection_done or force:
            try:
                # force a connection to the server
                self.connection_done = self.nova_client.authenticate()
            except Exception as e:
                log_error("Cannot connect to cinder: %s\n" % e)

    def _set_stats(self, cinder, meth):
        for keys in ['_count', '_size', '_status', '_attached', '_bootable']:
            if find(meth, 'snapshots') >= 0:
                if keys in ['_attached', '_bootable']:
                    continue
            if hasattr(cinder, 'volume_type'):
                # TODO: "None" type are all the volumes before the
                # switch to multi-backend.  Cannot do a thing about
                # them.  Maybe add a DefaultBackend option to the
                # script.  Or Just add the proper property to the
                # volume.
                dyn_key = cinder.volume_type + '.' + meth + keys
            else:
                dyn_key = meth + keys

            if find(keys, 'status') >= 0:
                dyn_key = dyn_key + '.' + cinder.status

            if dyn_key not in self.stats:
                self.stats[dyn_key] = 0
            if find(keys, 'size') >= 0:
                self.stats[dyn_key] += cinder.size
            elif find(keys, 'attached') >= 0:
                self.stats[dyn_key] += len(cinder.attachments)
            elif find(keys, 'boot') >= 0:
                if cinder.bootable and cinder.bootable not in ['false', 'False']:
                    self.stats[dyn_key] += 1
            else:
                self.stats[dyn_key] += 1

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
    global config
    error = "%s [error]: %s" % (plugin_name, msg)
    collectd.error(error)
    config['error'] = error


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
        elif node.key == 'VolumeType':
            config['volume_type'] = node.values[0]
        else:
            collectd.warning('nova_hypervisor_stats_info plugin: Unknown config key: %s.'
                             % node.key)
    if not config.has_key('auth_url'):
        log_error('AuthURL not defined')

    if not config.has_key('username'):
        log_error('Username not defined')

    if not config.has_key('password'):
        log_error('Password not defined')

    if not config.has_key('tenant'):
        log_error('Tenant not defined')

    log_verbose('Configured with auth_url=%s, username=%s, password=%s, tenant=%s, endpoint_type=%s,volume_type=%s' % (config['auth_url'], config['username'], config['password'], config['tenant'], config['endpoint_type'], config['volume_type']))


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
        
    except Exception as e:
        log_error("Error creating cinder communication object: %s" % e)
        return


    config['util'] = Novautils(nova_client)
    config['util'].check_connection()


def init_callback():
    """Initialization block"""
    global config
    connect(config)
    log_verbose('Got a valid connection to nova API')


def read_callback(data=None):
    if config['error']:
        log_warning("Got a error during initialization.  Fix it and restart collectd")
        return
    if not config.has_key('util'):
        config['util'] = Novautils(nova_client)
        config['util'].check_connection()
        return
    info = config['util'].get_stats(config['volume_type'])
    log_verbose(pformat(info))
    for key in info:
        dispatch_value(key, info[key], 'gauge', config['metric_name'], config['util'].last_stats)

collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)

