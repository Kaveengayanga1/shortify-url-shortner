variable "aws_region" {
  description = "AWS region to create everything in."
  type        = string
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform state. MUST be globally unique."
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name for state locking."
  type        = string
}