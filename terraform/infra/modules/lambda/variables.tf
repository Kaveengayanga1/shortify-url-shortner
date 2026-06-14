variable "function_name" { type = string }
variable "source_dir"    { type = string }

variable "handler" {
  type    = string
  default = "handler.lambda_handler"
}
variable "runtime" {
  type    = string
  default = "python3.13"
}
variable "timeout" {
  type    = number
  default = 10
}
variable "memory_size" {
  type    = number
  default = 128
}
variable "log_retention_days" {
  type    = number
  default = 14
}
variable "environment" {
  type    = map(string)
  default = {}
}
variable "table_arn" {
  type    = string
  default = ""
}
variable "dynamodb_actions" {
  type    = list(string)
  default = []
}

variable "enable_tracing" {
  type    = bool
  default = false
}