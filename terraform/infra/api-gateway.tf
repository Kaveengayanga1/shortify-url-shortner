resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  # HTTP API answers browser preflight (OPTIONS) for you — no extra route needed.
  cors_configuration {
    allow_origins = ["*"] # tighten to your real frontend origin later
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }

}

resource "aws_apigatewayv2_integration" "create" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = module.create_fn.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "create" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /urls"
  target    = "integrations/${aws_apigatewayv2_integration.create.id}"
}

# API Gateway is a separate service, so it needs explicit permission to call
# the Lambda. Without this you get 500s with no useful error.
resource "aws_lambda_permission" "create" {
  statement_id  = "AllowInvokeCreateFromHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = module.create_fn.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "api_base_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}


resource "aws_apigatewayv2_integration" "redirect" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = module.redirect_fn.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "redirect" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /{code}"
  target    = "integrations/${aws_apigatewayv2_integration.redirect.id}"
}

resource "aws_lambda_permission" "redirect" {
  statement_id  = "AllowInvokeRedirectFromHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = module.redirect_fn.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}