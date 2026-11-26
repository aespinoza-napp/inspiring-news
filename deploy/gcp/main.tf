# Everything around the VM: the APIs it needs, its identity, and the
# secrets it reads at boot. The VM itself is in vm.tf, its network in
# network.tf, the alerts in monitoring.tf. docs/decisions/deployment.md
# has the reasoning; ./scripts/check.sh gcp applies all of it to Floci.

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "storage.googleapis.com",
  ])

  service = each.value

  # Destroying this deployment must not switch an API off for anything
  # else in the project.
  disable_on_destroy = false
}

# The VM's own identity: it can read its four secrets and write logs and
# metrics, and nothing else. Not the default compute service account,
# which has Editor on the whole project.
resource "google_service_account" "vm" {
  account_id   = "${var.name}-vm"
  display_name = "Inspiring News VM"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "vm" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.vm.email}"
}

# ---------------------------------------------------------------------
# Secrets. Generated here, so no one types them and none is committed:
# they live in the Terraform state and in Secret Manager, and the VM
# renders backend/.env from Secret Manager on every boot
# (deploy/gcp/vm/bootstrap.sh). The state therefore holds secrets too -
# keep it out of git (deploy/gcp/.gitignore) or in a GCS backend.
# ---------------------------------------------------------------------

resource "random_password" "neo4j" {
  length  = 32
  special = false
}

# SearXNG's server secret: 64 hex characters, as docker/README.md tells
# a person to generate it.
resource "random_id" "searxng" {
  byte_length = 32
}

resource "random_password" "storage_api_key" {
  length  = 40
  special = false
}

# The site's password (user `editor`), in front of the whole UI: the
# frontend's server routes attach the API key to everything they
# forward, so an open frontend would be the backend with the key in it
# (docker/caddy/Caddyfile). Only its bcrypt hash goes to Secret Manager
# and the VM - Caddy's basic_auth takes nothing else. The password itself
# is `terraform output -raw site_password`. The hash is computed once and
# kept in the state: Terraform's bcrypt() function salts anew on every
# plan, and the secret would never stop changing.
resource "random_password" "site" {
  length  = 24
  special = false
}

locals {
  secrets = {
    "neo4j-password"     = random_password.neo4j.result
    "searxng-secret"     = random_id.searxng.hex
    "storage-api-key"    = random_password.storage_api_key.result
    "site-password-hash" = random_password.site.bcrypt_hash
  }

  # Given rather than generated, and only when given: bootstrap.sh reads
  # it with optional_secret. nonsensitive() on the test alone - the key
  # stays sensitive - since a map chosen by a sensitive condition would be
  # sensitive as a whole, and for_each refuses that.
  optional_secrets = nonsensitive(var.groq_api_key != "") ? { "groq-api-key" = var.groq_api_key } : {}

  all_secrets = merge(local.secrets, local.optional_secrets)
}

resource "google_secret_manager_secret" "stack" {
  for_each = local.all_secrets

  secret_id = "${var.name}-${each.key}"

  # Automatic, Google's default. Pinned to the region (`user_managed`)
  # was the first version, and Floci keeps only the replication type,
  # not its locations, so every plan after an apply wanted to replace
  # all three secrets. Three random strings hold no personal data: the
  # stricter residency was not worth a check that can never pass.
  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "stack" {
  for_each = local.all_secrets

  secret      = google_secret_manager_secret.stack[each.key].id
  secret_data = each.value
}

resource "google_secret_manager_secret_iam_member" "vm" {
  for_each = local.all_secrets

  secret_id = google_secret_manager_secret.stack[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vm.email}"
}

# ---------------------------------------------------------------------
# The seed: what a new VM starts from (deploy/gcp/vm/bootstrap.sh, seed).
# scripts/gcp_seed.sh uploads the graph's dump, the lake and the import's
# photos from the dev machine; the first boot restores them into volumes
# that do not exist yet, never over what the VM wrote. Private: the VM
# reads it with its own account, no one else is granted anything.
# ---------------------------------------------------------------------

resource "google_storage_bucket" "seed" {
  # Bucket names are global, hence the project in it.
  name     = "${var.project_id}-${var.name}-seed"
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  # A copy of what the dev machine holds, made again by gcp_seed.sh: a
  # destroy should not stop at it.
  force_destroy = true

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "seed" {
  bucket = google_storage_bucket.seed.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.vm.email}"
}
