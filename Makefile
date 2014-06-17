PLUGIN = collectd-nova-hypervisor-stats.py
PLUGIN_DIR = lib
VERSION := $(shell cat $(PLUGIN_DIR)/$(PLUGIN) | egrep ^'version =' | cut -d ' ' -f 3 | cut -d \" -f 2)
PREFIX ?= /opt/collectd-nova-hypervisor-stats-$(VERSION)

install:
#	@install -d $(PREFIX)/$(PLUGIN_DIR)
#	@install $(PLUGIN_DIR)/$(PLUGIN) $(PREFIX)/$(PLUGIN_DIR)
	@echo "Installed collected-nova-hypervisor-stats plugin, add this"
	@echo "to your collectd configuration to load this plugin:"
	@echo
	@echo ' <LoadPlugin "python">'
	@echo '     Globals true'
	@echo ' </LoadPlugin>'
	@echo
	@echo ' <Plugin "python">'
	@echo ' # $(PLUGIN) is at $(PREFIX)/$(PLUGIN_DIR)/$(PLUGIN)'
	@echo ' ModulePath "$(PREFIX)/$(PLUGIN_DIR)"'
	@echo
	@echo ' Import "collectd-nova-hypervisor-stats"'
	@echo
	@echo ' <Module "collectd-nova-hypervisor-stats">'
	@echo '        AuthURL   "http://myopenstack.cloud.home:5000/v2.0"'
	@echo '        Username  "admin"'
	@echo '        Password  "hardhard"'
	@echo '        Tenant    "admin"'
	@echo ' </Module>'
	@echo ' </Plugin>'
