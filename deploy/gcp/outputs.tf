output "external_ip" {
  description = "Point the domain's A record here; without one, http://<ip>/healthz answers."
  value       = google_compute_address.vm.address
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
