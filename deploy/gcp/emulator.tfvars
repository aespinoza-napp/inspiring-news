# ./scripts/check.sh gcp applies the module with these, against Floci.
# Not a deployment: Floci manages VMs but runs no guest.
#
# The stack about to be deployed: lite, with Groq's key and the sslip.io
# names. The check plans the full stack as well, without applying it.
project_id        = "floci-local"
emulator_endpoint = "http://floci-gcp:4588"

stack          = "lite"
free_hostnames = true
groq_api_key   = "gsk-emulator-not-a-key"

# Floci's fixture machine catalog has no E2 types; this one it has
# (4 vCPU, 16 GB). The real lite default is e2-standard-2.
machine_type = "n2-standard-4"
