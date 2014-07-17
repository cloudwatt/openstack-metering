#!/usr/bin/env python

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
