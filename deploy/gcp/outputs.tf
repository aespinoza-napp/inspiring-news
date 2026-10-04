output "external_ip" {
  description = "Point the domain's A record here; without one, http://<ip>/healthz answers."
  value       = google_compute_address.vm.address
}

output "site_url" {
  description = "The UI, over HTTPS, once the domain's A record points at external_ip. Without a domain there is none: use ui_tunnel."
  value       = var.domain != "" ? "https://${var.domain}/" : "(no domain: only http://${google_compute_address.vm.address}/healthz is public - use ui_tunnel)"
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
