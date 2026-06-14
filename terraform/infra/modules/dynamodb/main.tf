resource "aws_dynamodb_table" "urls" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST" # no capacity to manage; pay per request. Great for dev.
  hash_key     = "PK"
  range_key    = "SK"

  # Only KEY attributes are declared. Everything else is schemaless.
  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "GSI1PK"
    type = "S"
  }
  attribute {
    name = "GSI1SK"
    type = "S"
  }

  # Secondary index that answers "list all links by this owner".
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL" # the index returns all fields of the item
  }

  # Auto-delete items once this field's time has passed.
  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }

  tags = {
    Name = var.table_name
  }
}