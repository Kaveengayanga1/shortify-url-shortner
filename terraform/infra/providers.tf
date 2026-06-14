terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # These tags get added to every resource automatically.
  # Handy for finding your project's resources later.
  default_tags {
    tags = {
      Project   = "url-shortener"
      ManagedBy = "terraform"
    }
  }
}