# One VM running the same compose stack as everywhere else
# (docker-compose.yml + .prod.yml + .gcp.yml). Not Cloud Run: the stack
# is stateful in ways a request-scoped container is not - Qdrant's local
# storage takes a file lock, JobStore is in memory, analyses run in
# background threads after the response, and inference/ plus the LLM
# want ~6 GiB resident and warm. docs/decisions/deployment.md.

locals {
  # Floci has no public OS image catalog, so under the emulator the VM
  # boots from an image made from a blank disk. Only the API calls are
  # being exercised there; no guest ever runs.
  boot_image = local.emulated ? google_compute_image.emulator_seed[0].self_link : var.boot_image

  site_address = var.domain != "" ? var.domain : ":80"
}

resource "google_compute_disk" "emulator_seed" {
  count = local.emulated ? 1 : 0

  name = "${var.name}-emulator-seed"
  zone = var.zone
  type = "pd-standard"
  size = 10
}

resource "google_compute_image" "emulator_seed" {
  count = local.emulated ? 1 : 0

  name        = "${var.name}-emulator-seed"
  source_disk = google_compute_disk.emulator_seed[0].self_link
}

resource "google_compute_instance" "vm" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = [var.name]
  labels       = { app = var.name }

  # A machine-type change stops and starts the VM instead of replacing
  # it - replacing it would replace the boot disk, and the lake with it.
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = local.boot_image
      size  = var.boot_disk_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.vm.id

    access_config {
      nat_ip = google_compute_address.vm.address
    }
  }

  service_account {
    email = google_service_account.vm.email
    # The account's roles are what limit it (main.tf); this scope only
    # lets the VM use them.
    scopes = ["cloud-platform"]
  }

  metadata = {
    # In metadata, not metadata_startup_script: a change here then
    # updates the instance in place rather than recreating it.
    #
    # CRs stripped: applied from a Windows checkout made before
    # .gitattributes pinned *.tftpl to LF, the template is CRLF, and the
    # VM's bash reads "pipefail\r" as an unknown option on line one.
    startup-script = replace(templatefile("${path.module}/startup.sh.tftpl", {
      repo_url      = var.repo_url
      repo_ref      = var.repo_ref
      project_id    = var.project_id
      secret_prefix = var.name
      llm_model     = var.llm_model
      site_address  = local.site_address
    }), "\r", "")
    enable-oslogin = "TRUE"
  }

  # The secrets must be readable before the first boot renders .env.
  depends_on = [
    google_secret_manager_secret_version.stack,
    google_secret_manager_secret_iam_member.vm,
  ]
}

# ---------------------------------------------------------------------
# Backups: daily snapshots of the boot disk, which holds every volume -
# the lake and Qdrant's corpus (the record), the graph (rebuildable with
# POST /graph/sync) and the model caches. Crash-consistent, kept
# `snapshot_retention_days`. Not emulated by Floci, so skipped there.
# ---------------------------------------------------------------------

resource "google_compute_resource_policy" "snapshots" {
  count = local.emulated ? 0 : 1

  name   = "${var.name}-daily"
  region = var.region

  snapshot_schedule_policy {
    schedule {
      daily_schedule {
        days_in_cycle = 1
        start_time    = "03:00"
      }
    }
    retention_policy {
      max_retention_days    = var.snapshot_retention_days
      on_source_disk_delete = "KEEP_AUTO_SNAPSHOTS"
    }
    snapshot_properties {
      storage_locations = [var.region]
    }
  }
}

resource "google_compute_disk_resource_policy_attachment" "snapshots" {
  count = local.emulated ? 0 : 1

  name = google_compute_resource_policy.snapshots[0].name
  disk = google_compute_instance.vm.name
  zone = var.zone
}
