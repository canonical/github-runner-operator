# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Top-level Makefile
# Delegates targets to Makefile.docs

# ==============================================================================
# Macros
# ==============================================================================

# Colors
NO_COLOR=\033[0m
CYAN_COLOR=\033[0;36m
YELLOW_COLOR=\033[0;93m
RED_COLOR=\033[0;91m

msg = @printf '$(CYAN_COLOR)$(1)$(NO_COLOR)\n'
errmsg = @printf '$(RED_COLOR)Error: $(1)$(NO_COLOR)\n' && exit 1

# ==============================================================================
# Core
# ==============================================================================

include Makefile.docs

.PHONY: help 
help: _list-targets ## Prints all available targets

.PHONY: _list-targets
_list-targets: ## This collects and prints all targets, ignore internal commands
	$(call msg,Available targets:)
	@awk -F'[:#]' '                                               \
		/^[a-zA-Z0-9._-]+:([^=]|$$)/ {                            \
			target = $$1;                                         \
			comment = "";                                         \
			if (match($$0, /## .*/))                              \
				comment = substr($$0, RSTART + 3);                \
			if (target != ".PHONY" && target !~ /^_/ && !seen[target]++) \
				printf "  make %-20s $(YELLOW_COLOR)# %s$(NO_COLOR)\n", target, comment;    \
		}' $(MAKEFILE_LIST) | sort

