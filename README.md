# Introduction

Collectd plugin that get the equivalent of `nova hypervisor-stats`.

# Installation

    make install

or

    PREFIX=/opt/collectd make install


# Configuration

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
* `Username` - The user to use to log in (must have admin right);
* `Password` - Well .... the password;
* `Tenant` - Tenant to use

The following parameters are optional:
* `EndpointType` - The type of the endpoint.  By default "publicURL".
* `MetricName` - Choose the name of the metric.  'nova.hypervisor_stats' by default.
* `Verbose` - Add some verbosity, visible in the collectd logs.

# Graph examples

This was done using [Librato collectd plugin](https://github.com/librato/collectd-librato)

![CPUs](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_cpus.png)
![RAM](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_ram.png)
![disk](https://raw.githubusercontent.com/enovance/collectd-nova-hypervisor-stats/master/screenshots/graph_disk.png)
