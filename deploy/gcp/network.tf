# A network of its own rather than the project's "default": the default
# network ships firewall rules that open SSH and RDP to the whole
# internet. Custom-mode, so the one subnet is the only one there is.

resource "google_compute_network" "vpc" {
  name                    = var.name
  auto_create_subnetworks = false

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "vm" {
  name          = var.name
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = "10.10.0.0/24"
}

# 80 and 443 reach Caddy (docker/caddy/Caddyfile): /healthz, and with a
# domain the UI over HTTPS behind a password; 80 also answers the ACME
# challenge and redirects to 443. Every other port in the stack - the
# API's 8000, the UI's 3000 - stays on the compose network or the VM's
# loopback.
resource "google_compute_firewall" "web" {
  name          = "${var.name}-web"
  network       = google_compute_network.vpc.id
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}

# SSH only through Identity-Aware Proxy (`gcloud compute ssh --tunnel-through-iap`),
# whose source range this is. That is also how to reach the Neo4j console:
# an IAP tunnel, then `docker compose exec`.
resource "google_compute_firewall" "ssh_iap" {
  name          = "${var.name}-ssh-iap"
  network       = google_compute_network.vpc.id
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [var.name]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Static, so a domain's DNS record and the uptime check survive the VM
# being recreated.
resource "google_compute_address" "vm" {
  name   = var.name
  region = var.region
}
