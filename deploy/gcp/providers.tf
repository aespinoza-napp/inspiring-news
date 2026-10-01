locals {
  # Against Floci (./scripts/check.sh gcp) every API this module calls is
  # redirected to the emulator; against Google Cloud every override is
  # null, which is the provider's own default.
  emulated = var.emulator_endpoint != ""
  endpoint = trimsuffix(var.emulator_endpoint, "/")
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  user_project_override = false

  compute_custom_endpoint          = local.emulated ? "${local.endpoint}/compute/v1/" : null
  secret_manager_custom_endpoint   = local.emulated ? "${local.endpoint}/v1/" : null
  iam_custom_endpoint              = local.emulated ? "${local.endpoint}/" : null
  iam_beta_custom_endpoint         = local.emulated ? "${local.endpoint}/v1/" : null
  resource_manager_custom_endpoint = local.emulated ? "${local.endpoint}/v1/" : null
  service_usage_custom_endpoint    = local.emulated ? "${local.endpoint}/v1/" : null
}
