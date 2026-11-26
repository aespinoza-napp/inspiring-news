output "external_ip" {
  description = "Point the domain's A record here; without one, http://<ip>/healthz answers."
  value       = google_compute_address.vm.address
}

output "site_url" {
  description = "The newsroom's UI (/discover among it), over HTTPS behind the password, once its name points at external_ip. Without a name there is none: use ui_tunnel."
  value       = local.site_address != ":80" ? "https://${local.site_address}/" : "(no domain: only http://${google_compute_address.vm.address}/healthz and /reader are public - use ui_tunnel)"
}

output "universe_url" {
  description = "The readers' universe, open to anyone. Over plain HTTP when it has no name: browsing works, signing in does not."
  value       = startswith(local.universe_address, "http://") ? "${local.universe_address}/" : "https://${local.universe_address}/"
}

output "machine_type" {
  value = local.machine_type
}

output "seed_bucket" {
  description = "Where scripts/gcp_seed.sh uploads the graph, the lake and the photos for the first boot."
  value       = google_storage_bucket.seed.name
}

output "seed_command" {
  description = "Run on the dev machine after applying the bucket and before the VM exists (docs/decisions/deployment.md, \"The first deploy\"): the VM restores the seed only into volumes it has not created yet."
  value       = "./scripts/gcp_seed.sh ${google_storage_bucket.seed.name}"
}

output "ui_tunnel" {
  # The UI and the API on the VM's loopback, forwarded to this machine
  # through Identity-Aware Proxy: http://127.0.0.1:3000 is the site (no
  # password - the tunnel is the access control), http://127.0.0.1:8000
  # the API (with storage_api_key). Works with or without a domain.
  description = "Run it, leave it open, browse http://127.0.0.1:3000."
  value       = "gcloud compute ssh ${var.name} --zone ${var.zone} --tunnel-through-iap -- -N -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000"
}

output "ssh" {
  value = "gcloud compute ssh ${var.name} --zone ${var.zone} --tunnel-through-iap"
}

output "follow_first_boot" {
  description = "The first boot builds the images and downloads ~10 GB of models: 20-30 minutes."
  value       = "gcloud compute ssh ${var.name} --zone ${var.zone} --tunnel-through-iap --command 'sudo journalctl -u google-startup-scripts -f'"
}

output "secret_names" {
  value = { for key, secret in google_secret_manager_secret.stack : key => secret.secret_id }
}

output "storage_api_key" {
  description = "The X-API-Key the frontend's server routes must send. `terraform output -raw storage_api_key`."
  value       = random_password.storage_api_key.result
  sensitive   = true
}

output "site_password" {
  description = "The site's password, for user `editor` (docker/caddy/Caddyfile). `terraform output -raw site_password`."
  value       = random_password.site.result
  sensitive   = true
}
