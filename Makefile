.PHONY: build-index test-index sync-roles clean help

SKILL_DIR := skills/preflight
ROLES_DIR := $(SKILL_DIR)/roles
INDEX     := $(ROLES_DIR)/index.json
PARSER    := scripts/frontmatter-to-json.awk

help:
	@echo "preflight — make targets:"
	@echo "  sync-roles    Fetch upstream community prompts and wrap for preflight."
	@echo "  build-index   Regenerate $(INDEX) from roles/*.md frontmatter."
	@echo "  test-index    Assert index is non-empty and schema-valid."
	@echo "  clean         Remove generated index."

sync-roles:
	@command -v python3 >/dev/null 2>&1 || { echo "python3 not installed"; exit 1; }
	@python3 scripts/sync_roles.py $(ROLE)
	@$(MAKE) build-index

build-index:
	@command -v jq >/dev/null 2>&1 || { echo "jq not installed (brew install jq)"; exit 1; }
	@test -f $(PARSER) || { echo "missing $(PARSER)"; exit 1; }
	@printf '[' > $(INDEX).tmp
	@first=1; \
	for f in $(ROLES_DIR)/*.md; do \
	  entry=$$(awk -f $(PARSER) "$$f"); \
	  if [ -z "$$entry" ]; then \
	    echo "WARN: $$f has no YAML frontmatter, skipping" >&2; continue; \
	  fi; \
	  if ! echo "$$entry" | jq -e . >/dev/null 2>&1; then \
	    echo "FAIL: $$f produced invalid JSON: $$entry" >&2; exit 1; \
	  fi; \
	  if [ $$first -eq 0 ]; then printf ',' >> $(INDEX).tmp; fi; \
	  printf '%s' "$$entry" >> $(INDEX).tmp; \
	  first=0; \
	done
	@printf ']' >> $(INDEX).tmp
	@jq '.' $(INDEX).tmp > $(INDEX) && rm $(INDEX).tmp
	@echo "Wrote $(INDEX) ($$(jq 'length' $(INDEX)) roles)"

test-index: build-index
	@test -s $(INDEX) || { echo "FAIL: $(INDEX) is empty"; exit 1; }
	@jq -e 'length > 0' $(INDEX) >/dev/null || { echo "FAIL: $(INDEX) has 0 roles"; exit 1; }
	@jq -e 'all(.[]; has("name") and has("when_to_pick") and has("tags"))' $(INDEX) >/dev/null \
	  || { echo "FAIL: some roles missing required frontmatter fields (name, when_to_pick, tags)"; exit 1; }
	@echo "OK: $(INDEX) has $$(jq 'length' $(INDEX)) valid roles"

clean:
	@rm -f $(INDEX) $(INDEX).tmp
