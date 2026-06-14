module "dynamodb" {
  source     = "./modules/dynamodb"
  table_name = "${var.project_name}-urls" # becomes "shortify-urls"
}


module "create_fn" {
  source           = "./modules/lambda"
  function_name    = "${var.project_name}-create"
  source_dir       = "${path.root}/../../app/src/create"
  table_arn        = module.dynamodb.table_arn
  dynamodb_actions = ["dynamodb:PutItem"]
  environment = {
    TABLE_NAME = module.dynamodb.table_name
  }
}

module "redirect_fn" {
  source           = "./modules/lambda"
  function_name    = "${var.project_name}-redirect"
  source_dir       = "${path.root}/../../app/src/redirect"
  table_arn        = module.dynamodb.table_arn
  dynamodb_actions = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
  environment = {
    TABLE_NAME = module.dynamodb.table_name
  }
}

