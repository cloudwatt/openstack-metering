PREFIX ?= /opt/openstack-metrics

PLUGINS = collectd-nova-hypervisor-stats.py collectd-nova-aggregate.py
PLUGINS += collectd-neutron-floatingips.py collectd-keystone-stats.py
PLUGINS += collectd-cinder-stats.py
PLUGINS_FULL = $(addprefix $(PREFIX)/, $(PLUGINS))

PLUGIN_DIR = lib

.DEFAULT: all

all: $(PLUGINS_FULL)
	@echo ''
	@echo ''
	@echo 'See README for more details'

$(PREFIX):
	install -d $(PREFIX)

$(PLUGINS_FULL): $(PREFIX)
	@echo ''
	install $(PLUGIN_DIR)/$(subst $(PREFIX)/,,$@) $@
	@echo ''
	@echo "Installed $(subst $(PREFIX)/,,$@) plugin, add this"
	@echo "to your collectd configuration to load this plugin:"
	@echo
	@echo ' <LoadPlugin "python">'
	@echo '     Globals true'
	@echo ' </LoadPlugin>'
	@echo
	@echo ' <Plugin "python">'
	@echo ' # $(PLUGIN) is at $@'
	@echo ' ModulePath "$(PREFIX)/"'
	@echo
	@echo ' Import "$(subst .py,,$(subst $(PREFIX)/,,$@))"'
	@echo
	@echo ' <Module "$(subst .py,,$(subst $(PREFIX)/,,$@))">'
	@echo '        AuthURL   "http://myopenstack.cloud.home:5000/v2.0"'
	@echo '        Username  "admin"'
	@echo '        Password  "hardhard"'
	@echo '        Tenant    "admin"'
	@echo ' </Module>'
	@echo ' </Plugin>'
