# Thin wrapper over scripts/check.sh so `make check` works too. The
# script is the source of truth - it runs anywhere bash does, including
# Git Bash on Windows where make usually is not installed.

.PHONY: check fast backend frontend

check:
	@./scripts/check.sh all

fast:
	@./scripts/check.sh fast

backend:
	@./scripts/check.sh backend

frontend:
	@./scripts/check.sh frontend
