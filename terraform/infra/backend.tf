terraform {
  backend "s3" {
    bucket         = "shortify-url-shortener-tf-state"
    key            = "url-shortener/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "shortify-url-shortener-tf-lock"
    encrypt        = true
  }
}