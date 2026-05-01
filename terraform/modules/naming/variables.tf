variable "project" {
  type        = string
  description = "Short project code, lowercase. Used as the middle segment of every resource name (e.g. 'art' → 'rg-art-dev')."
  validation {
    condition     = can(regex("^[a-z0-9]{2,12}$", var.project))
    error_message = "project must be 2–12 lowercase letters/digits, no dashes."
  }
}

variable "environment" {
  type        = string
  description = "Environment short name. Use 'dev', 'int', or 'prod' to keep all resources in the same convention across environments."
  validation {
    condition     = contains(["dev", "int", "prod"], var.environment)
    error_message = "environment must be one of: dev, int, prod."
  }
}

variable "suffix" {
  type        = string
  description = "Unique suffix appended to globally-unique resources (Web Apps, Storage Accounts, Key Vaults, etc.). Lowercase letters/digits only — Storage Accounts forbid dashes."
  validation {
    condition     = can(regex("^[a-z0-9]{4,8}$", var.suffix))
    error_message = "suffix must be 4–8 lowercase letters/digits (no dashes, no uppercase). Example: 'hp7k2a'."
  }
}
