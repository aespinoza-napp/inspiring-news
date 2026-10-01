terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source = "hashicorp/google"
      # The line floci-gcp's own Terraform compatibility suite runs on,
      # so the emulator check exercises the provider real deploys use.
      version = "~> 7.36"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}
