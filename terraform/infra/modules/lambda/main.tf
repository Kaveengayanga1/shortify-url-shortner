# Zip the function's source folder. boto3 is provided by the runtime, so the
# zip is just our own code.
data "archive_file" "zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/build/${var.function_name}.zip"
  excludes    = ["__pycache__"]
}

# A role the Lambda runs as. The "assume role" part says: only the Lambda
# service is allowed to use this role.
resource "aws_iam_role" "this" {
  name = "${var.function_name}-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Lets the function write its logs to CloudWatch. This is the standard minimum.
resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Only the exact DynamoDB actions this function needs, on only our table.
resource "aws_iam_role_policy" "dynamodb" {
  count = length(var.dynamodb_actions) > 0 ? 1 : 0
  name  = "${var.function_name}-dynamodb"
  role  = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = var.dynamodb_actions
      Resource = var.table_arn
    }]
  })
}

resource "aws_lambda_function" "this" {
  function_name    = var.function_name
  role             = aws_iam_role.this.arn
  handler          = var.handler
  runtime          = var.runtime
  filename         = data.archive_file.zip.output_path
  source_code_hash = data.archive_file.zip.output_base64sha256
  timeout          = var.timeout
  memory_size      = var.memory_size

  environment {
    variables = var.environment
  }

  dynamic "tracing_config" {
    for_each = var.enable_tracing ? [1] : []
    content { mode = "Active" }
  }

}

# Create the log group ourselves so we control retention (otherwise Lambda
# makes one that keeps logs forever).
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy_attachment" "xray" {
  count      = var.enable_tracing ? 1 : 0
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}