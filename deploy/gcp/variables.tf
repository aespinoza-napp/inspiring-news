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

variable "machine_type" {
  # 4 vCPU, 16 GB. 16 GB is the measured requirement: the stack's working
  # sets add up to ~6.1 GiB, ~8.4 GiB with caches, and ~9.6 GiB were
  # resident on the first production run (docs/decisions/deployment.md).
  description = "16 GB is the floor; see docs/decisions/deployment.md."
  type        = string
  default     = "e2-standard-4"
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
