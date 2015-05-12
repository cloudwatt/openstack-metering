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
import novaclient.client as nova
import glanceclient.client as glance
from keystoneclient.v2_0 import client as keystone
from datetime import datetime
from time import mktime
from pprint import pformat
import itertools

plugin_name = 'collectd-instances-stats'

version = '0.1.0'

config = {
    'endpoint_type': "internalURL",
    'verbose_logging': False,
    'image_filters': {}
}


class OpenstackUtils:
    STATUS = [
        'ACTIVE',
        'BUILD',
        'ERROR',
        'HARD_REBOOT',
        'PASSWORD',
        'REBOOT',
        'REBUILD',
        'RESCUE',
        'RESIZE',
        'REVERT_RESIZE',
        'SHUTOFF',
        'SUSPENDED',
        'UNKNOWN',
        'VERIFY_RESIZE'
    ]

    def __init__(self):
        self.last_stats = None
        self.connection_done = None

    def connect(self, config):
        ksclient = keystone.Client(username=config['username'],
                                   tenant_name=config['tenant'],
                                   password=config['password'],
                                   auth_url=config['auth_url'])

        compute_endpoint = ksclient.service_catalog.url_for(
                               service_type='compute',
                               endpoint_type=config['endpoint_type']
                           )

        image_endpoint = ksclient.service_catalog.url_for(
                             service_type='image',
                             endpoint_type=config['endpoint_type']
                         )

        nova_client = nova.Client('1.1',
                                  username=config['username'],
                                  auth_url=config['auth_url'],
                                  api_key='',
                                  project_id=config['tenant'],
                                  bypass_url=compute_endpoint,
                                  auth_token=ksclient.auth_token)

        glance_client = glance.Client('1',
                                      endpoint=image_endpoint,
                                      token=ksclient.auth_token)

        return nova_client, glance_client

    def get_stats(self):
        nova_client, glance_client = self.connect(config)

        self.last_stats = int(mktime(datetime.now().timetuple()))

        images = {}
        for image in glance_client.images.list(
                         filters={'visibility': 'public',
                                  'properties': config['image_filters'],
                                  'member_status': 'all'}):
            images[image.id] = image.name

        flavors = {}
        for flavor in nova_client.flavors.list():
            flavors[flavor.id] = flavor.name

        stats = {
            'instances': {k.lower():0 for k in OpenstackUtils.STATUS},
            'images': {k:0 for k in images.values()},
            'flavors': {k:0 for k in flavors.values()},
            'boot': {'ephemeral': 0, 'volume': 0}
        }

        for vm in nova_client.servers.list(search_opts={'all_tenants':1}):
            status = vm.status.lower()
            stats['instances'][status] = stats['instances'].setdefault(status, 0) + 1
            stats['instances']['total_count'] = \
                stats['instances'].setdefault('total_count', 0) + 1
            flavor = flavors[vm.flavor['id']]
            stats['flavors'][flavor] = stats['flavors'].setdefault(flavor, 0) + 1
            if type(vm.image) is dict and vm.image.has_key('id') and images.has_key(vm.image['id']):
                image = images[vm.image['id']]
                stats["images"][image] = stats["images"].setdefault(image, 0) + 1
                stats['boot']['ephemeral'] += 1
            else:
                stats['boot']['volume'] += 1

        return stats


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
        elif node.key == 'ImageFilter':
            config['image_filters'][node.values[0]] = node.values[1]
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


def init_callback():
    """Initialization block"""
    config['util'] = OpenstackUtils()
    config['util'].connect(config)


def read_callback(data=None):
    log_verbose("read_callback called")
    if 'util' not in config:
        log_error("Problem during initialization, fix and restart collectd.")
    info = config['util'].get_stats()
    log_verbose(pformat(info))
    for type_instance in info:
        dispatch_value(info[type_instance],
                       'nova',
                       config['util'].last_stats,
                       type_instance,
                       type_instance,
                       '',
                       'openstack')
    log_verbose("Leaving read_callback")


collectd.register_config(configure_callback)
collectd.register_init(init_callback)
collectd.register_read(read_callback)
