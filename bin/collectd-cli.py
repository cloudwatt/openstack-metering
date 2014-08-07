#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Collectd command line interface
#
# A litle utility is given to run the plugin on the command line in the bin
# directory. To use it give the collectd script as argument and some other
# required parameters.
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
import argparse
import datetime

parser = argparse.ArgumentParser(
    description='Run the collectd at the command line')
parser.add_argument('--script', metavar='script', type=str,
                    help='Which script to load. ')

parser.add_argument('--auth_url', metavar='URL', type=str,
                    required=True,
                    help='Keystone URL')

parser.add_argument('--username', metavar='username', type=str,
                    required=True,
                    help='username to use for authentication')

parser.add_argument('--password', metavar='password', type=str,
                    required=True,
                    help='password to use for authentication')

parser.add_argument('--tenant', metavar='tenant', type=str,
                    required=True,
                    help='tenant name to use for authentication')

parser.add_argument('--endpoint_type', metavar='endpoint_type', type=str,
                    default="publicURL",
                    help='Endpoint type in the catalog request. '
                    + 'Public by default.')


args = parser.parse_args()


class Collectd:
    """Proxy class """

    def __init__(self):
        self.values = []
        self.config = None
        self.init = None
        self.read = None

    def register_config(self, function):
        self.config = function

    def register_init(self, function):
        self.init = function

    def register_read(self, function):
        self.read = function

    def Values(self, **args):
        return Values(**args)

    def warning(self, msg):
        print(msg)

    def info(self, msg):
        print(msg)


class Configuration:
    """Proxy configuration class"""
    def __init__(self, args):
        self.children = [
            Node({'AuthURL': args.auth_url}),
            Node({'Username': args.username}),
            Node({'Password': args.password}),
            Node({'Tenant': args.tenant}),
            Node({'EndpointType': args.endpoint_type}),
        ]


class Node:
    """Proxy node class for configuration"""
    def __init__(self, entry):
        self.key = entry.keys()[0]
        self.values = entry.values()


class Values:
    def __init__(self, **args):
        self.host = ""
        self.plugin = ""
        self.plugin_instance = ""
        self.type = ""
        self.type_instance = ""
        self.time = datetime.utcnow()
        self.values = []

    def __str__(self):
        return "%s: %s.%s-%s.%s-%s = %s" % (
            self.time,
            self.host,
            self.plugin,
            self.plugin_instance,
            self.type,
            self.type_instance,
            self.values)

    def dispatch(self):
        print(self)

collectd = Collectd()

execfile(args.script)

conf = Configuration(args)

collectd.config(conf)
collectd.init()
collectd.read()
