# Introduction #

Collection of collectd plugin to get stats from openstack.

It currently consists of:

* `collectd-nova-hypervisor-stats`: get the equivalent of `nova hypervisor-stats`.
* `collectd-neutron-floatingips`: get the used and estimated total number of floating ip
* `collectd-cinder-stats`: get the equivalent of `cinder {snapshot-}list --all_tenant`


# Installation #

    make install

or

    PREFIX=/opt/collectd make install


# Configuration #

## collectd-nova-hypervisor-stats ##

Add the following to your collectd config and restart collectd.

     <LoadPlugin "python">
         Globals true
     </LoadPlugin>
    
     <Plugin "python">
     # collectd-nova-hypervisor-stats.py is at /usr/local/lib/collectd-nova-hypervisor-stats.py
     ModulePath "/usr/local/lib"
    
     Import "collectd-nova-hypervisor-stats"
    
     <Module "collectd-nova-hypervisor-stats">
            AuthURL   "http://myopenstack.cloud.home:5000/v2.0"
            Username  "admin"
            Password  "hardhard"
            Tenant    "admin"
     </Module>
     </Plugin>

The following parameters are required:

* `AuthURL` - The identity service for openstack;
* `Username` - The user to use to log in (must have admin role);
* `Password` - Well .... the password;
* `Tenant` - Tenant to use

The following parameters are optional:
* `EndpointType` - The type of the endpoint.  By default "publicURL".
* `MetricName` - Choose the name of the metric.  'nova.hypervisor_stats' by default.
* `Verbose` - Add some verbosity, visible in the collectd logs.

## collectd-neutron-floatingips ##

Add the following to your collectd config and restart collectd.

     <LoadPlugin "python">
         Globals true
     </LoadPlugin>
    
     <Plugin "python">
     ModulePath "/usr/local/lib"
    
     Import "collectd-neutron-floatingips"
    
     <Module "collectd-neutron-floatingips">
            AuthURL   "http://myopenstack.cloud.home:5000/v2.0"
            Username  "admin"
            Password  "hardhard"
            Tenant    "admin"
     </Module>
     </Plugin>

The following parameters are required:

* `AuthURL` - The identity service for openstack;
* `Username` - The user to use to log in (must have admin role);
* `Password` - Well .... the password;
* `Tenant` - Tenant to use

The following parameters are optional:
* `EndpointType` - The type of the endpoint.  By default "publicURL".
* `MetricName` - Choose the name of the metric.  'nova.hypervisor_stats' by default.
* `Verbose` - Add some verbosity, visible in the collectd logs.
* `PublicNetwork` - Used for calculating a estimation of floating ip available.  It's the name of the network where the public subnets are.  `public` by default, can be `none` to deactivate it.

The total number of floating ip is an estimate as I do not take into
account the IP allocation pool, where one can specify that only a part
of the floating ips of the subnet are available.  This speed up the
calculation and is usually a good enough estimate.  If you do not use
this feature (IP allocation pool), then the calcul is correct: it
removes two ips (network and broadcast) and if the gateway is enabled
a third one.

## collectd-neutron-floatingips ##

Add the following to your collectd config and restart collectd.

     <LoadPlugin "python">
         Globals true
     </LoadPlugin>
    
     <Plugin "python">
     ModulePath "/usr/local/lib"
    
     Import "collectd-neutron-floatingips"

     <Module "collectd-neutron-floatingips">
         AuthURL   "http://myopenstack.cloud.home:5000/v2.0"
         Username  "admin"
         Password  "hardhard"
         Tenant    "admin"
     </Module>
     </Plugin>

The following parameters are required:

* `AuthURL` - The identity service for openstack;
* `Username` - The user to use to log in (must have admin role);
* `Password` - Well .... the password;
* `Tenant` - Tenant to use

The following parameters are optional:
* `EndpointType` - The type of the endpoint.  By default "publicURL".
* `MetricName` - Choose the name of the metric.  'nova.hypervisor_stats' by default.
* `Verbose` - Add some verbosity, visible in the collectd logs.


# Graph examples #

## collectd-nova-hypervisor-stats ##

This was done using [Librato collectd plugin](https://github.com/librato/collectd-librato)

![CPUs](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_cpus.png)
![RAM](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_ram.png)
![disk](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_disk.png)

