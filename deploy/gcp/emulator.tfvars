# ./scripts/check.sh gcp applies the module with these, against Floci.
# Not a deployment: Floci manages VMs but runs no guest.
project_id        = "floci-local"
emulator_endpoint = "http://floci-gcp:4588"

# Floci's fixture machine catalog has no e2-standard-4; this is the same
# shape (4 vCPU, 16 GB).
machine_type = "n2-standard-4"
