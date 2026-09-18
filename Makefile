# Thin wrapper over scripts/check.sh and scripts/dev.sh so `make check`/
# `make dev` work too. The scripts are the source of truth - they run
# anywhere bash does, including Git Bash on Windows where make usually
# is not installed.

.PHONY: check fast slow backend frontend dev dev-docker stop

check:
	@./scripts/check.sh all

fast:
	@./scripts/check.sh fast

backend:
	@./scripts/check.sh backend

frontend:
	@./scripts/check.sh frontend

slow:
	@./scripts/check.sh slow

# Runs the app: docker services (backend, inference, searxng, neo4j)
# plus the frontend dev server. Not verification - see scripts/check.sh
# for that.
dev:
	@./scripts/dev.sh all

# Docker services only, detached - e.g. to run frontend separately in
# its own terminal.
dev-docker:
	@./scripts/dev.sh docker

stop:
	@./scripts/dev.sh stop
