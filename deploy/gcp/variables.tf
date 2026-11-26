variable "project_id" {
  description = "The Google Cloud project to deploy into."
  type        = string
}

variable "region" {
  description = "Madrid by default: the users and the paper are in Spain."
  type        = string
  default     = "europe-southwest1"
}

variable "zone" {
  type    = string
  default = "europe-southwest1-a"
}

variable "name" {
  description = "Prefix for every resource and secret name."
  type        = string
  default     = "inspiring-news"
}

variable "stack" {
  # full: the whole pipeline with its own LLM (Ollama), both graphs - 16 GB.
  # lite: the readers' universe and the newsroom's /discover, with Groq as
  # the LLM, no local model and no Devastating graph
  # (docker/docker-compose.lite.yml) - 8 GB. docs/decisions/deployment.md,
  # "The first deploy: the universe and /discover".
  description = "\"full\" or \"lite\" (the universe and /discover, Groq as the LLM)."
  type        = string
  default     = "full"

  validation {
    condition     = contains(["full", "lite"], var.stack)
    error_message = "stack is \"full\" or \"lite\"."
  }
}

variable "machine_type" {
  # By the stack when not given (vm.tf): e2-standard-4 (4 vCPU, 16 GB) for
  # full - its working sets add up to ~6.1 GiB, ~8.4 GiB with caches, and
  # ~9.6 GiB were resident on the first production run - and
  # e2-standard-2 (2 vCPU, 8 GB) for lite, whose caps add up to ~7.1 GB
  # without the LLM's ~3.2 GiB and the second graph's ~1 GB.
  description = "Empty: e2-standard-4 for the full stack, e2-standard-2 for lite. See docs/decisions/deployment.md."
  type        = string
  default     = ""
}

variable "boot_disk_gb" {
  # Images ~9 GB, model cache 7.4 GB, the LLM 2 GB, the graph and the
  # lake growing from there.
  type    = number
  default = 60
}

variable "boot_image" {
  type    = string
  default = "debian-cloud/debian-12"
}

variable "repo_url" {
  description = "Public repository the VM clones and builds from."
  type        = string
  default     = "https://github.com/aespinoza-napp/inspiring-news.git"
}

variable "repo_ref" {
  description = "Branch, tag or commit the VM checks out on every boot."
  type        = string
  default     = "main"
}

variable "llm_model" {
  type    = string
  default = "llama3.2:3b"
}

variable "domain" {
  # Without one, Caddy serves /healthz alone over plain HTTP, and the UI
  # only through `terraform output ui_tunnel`: the site's password must
  # not cross the internet in cleartext (docker/caddy/Caddyfile).
  description = "Optional. A name whose A record points at external_ip: Caddy gets its certificate and serves the UI over HTTPS, and the uptime check uses it. Empty: /healthz over HTTP only."
  type        = string
  default     = ""

  # Caddy's site address and the uptime check's host, verbatim: a scheme,
  # a path or a port would make both wrong without failing here.
  validation {
    condition     = var.domain == "" || can(regex("^([a-z0-9]([a-z0-9-]*[a-z0-9])?[.])+[a-z]{2,}$", var.domain))
    error_message = "domain is a bare hostname such as factcheck.example.org - no https://, path or port - or empty."
  }
}

variable "universe_domain" {
  # The readers' universe, open to anyone, at a name of its own (the
  # newsroom's site, `domain`, is behind a password). Empty: an sslip.io
  # name with free_hostnames, else plain HTTP on the VM's address.
  description = "Optional. A name whose A record points at external_ip, for the universe. Empty: see free_hostnames."
  type        = string
  default     = ""

  validation {
    condition     = var.universe_domain == "" || can(regex("^([a-z0-9]([a-z0-9-]*[a-z0-9])?[.])+[a-z]{2,}$", var.universe_domain))
    error_message = "universe_domain is a bare hostname such as universe.example.org - no https://, path or port - or empty."
  }
}

variable "free_hostnames" {
  # sslip.io answers any name with an address in it with that address
  # (34-175-1-2.sslip.io -> 34.175.1.2, and admin.34-175-1-2.sslip.io too),
  # so Caddy can get a real certificate with no domain bought. A third
  # party resolving the names, and Let's Encrypt's limits shared with its
  # other users: a way to start, not to stay.
  description = "With no domain: the universe at <ip>.sslip.io and the newsroom's site at admin.<ip>.sslip.io, both over HTTPS."
  type        = bool
  default     = false
}

variable "groq_api_key" {
  # Groq first (backend/src/services/llms.py); with the lite stack it is
  # the only LLM. Into Secret Manager like the generated ones, and into
  # the state: deploy/gcp/.gitignore keeps that out of git.
  description = "Optional; needed by the lite stack for the AI selection and analyses. From console.groq.com."
  type        = string
  default     = ""
  sensitive   = true
}

variable "alert_email" {
  description = "Optional. Where the uptime and search-health alerts go. Empty creates no monitoring resources."
  type        = string
  default     = ""
}

variable "snapshot_retention_days" {
  type    = number
  default = 7
}

variable "emulator_endpoint" {
  description = "Floci's address (e.g. http://floci-gcp:4588) to apply against the emulator instead of Google Cloud. Empty for a real deploy."
  type        = string
  default     = ""
}
