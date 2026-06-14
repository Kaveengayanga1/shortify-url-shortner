output "table_name" {
  value = aws_dynamodb_table.urls.name
}

output "table_arn" {
  value = aws_dynamodb_table.urls.arn
}

# We will need this exact string later for the Lambda's IAM permissions.
output "gsi1_arn" {
  value = "${aws_dynamodb_table.urls.arn}/index/GSI1"
}