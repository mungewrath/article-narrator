terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

resource "aws_sqs_queue" "jobs" {
  name                       = var.queue_name
  delay_seconds              = 0
  max_message_size           = 262144
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })

  tags = { Name = var.queue_name }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.queue_name}-dlq"
  message_retention_seconds = 1209600

  tags = { Name = "${var.queue_name}-dlq" }
}

data "aws_iam_policy_document" "api_gw_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["apigateway.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "api_gw_sqs" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.jobs.arn]
  }
}

resource "aws_iam_role" "api_gw_sqs" {
  name               = "${var.api_name}-api-gw-sqs"
  assume_role_policy = data.aws_iam_policy_document.api_gw_assume.json
}

resource "aws_iam_role_policy" "api_gw_sqs" {
  role   = aws_iam_role.api_gw_sqs.id
  policy = data.aws_iam_policy_document.api_gw_sqs.json
}

resource "aws_cognito_user_pool" "main" {
  name = var.api_name

  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true
    mutable             = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  tags = { Name = var.api_name }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.api_name}-${var.stage_name}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "frontend" {
  name                                 = "${var.api_name}-frontend"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false
  allowed_oauth_flows                  = ["implicit"]
  allowed_oauth_scopes                 = ["openid"]
  allowed_oauth_flows_user_pool_client = true
  callback_urls                        = concat(var.allowed_origins, ["https://${aws_cloudfront_distribution.main.domain_name}"])
  logout_urls                          = concat(var.allowed_origins, ["https://${aws_cloudfront_distribution.main.domain_name}"])
  supported_identity_providers         = ["COGNITO"]
}

resource "aws_api_gateway_rest_api" "main" {
  name        = var.api_name
  description = "Article Narrator submission API"

  endpoint_configuration { types = ["REGIONAL"] }
}

resource "aws_api_gateway_resource" "submit" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "submit"
}

resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${var.api_name}-cognito"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [aws_cognito_user_pool.main.arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_method" "submit_post" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.submit.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "submit_post" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.submit.id
  http_method             = aws_api_gateway_method.submit_post.http_method
  integration_http_method = "POST"
  type                    = "AWS"
  credentials             = aws_iam_role.api_gw_sqs.arn
  uri                     = "arn:aws:apigateway:${data.aws_region.current.region}:sqs:path/${data.aws_caller_identity.current.account_id}/${aws_sqs_queue.jobs.name}"

  request_parameters = {
    "integration.request.header.Content-Type" = "'application/x-www-form-urlencoded'"
  }

  request_templates = {
    "application/json" = <<-EOT
      Action=SendMessage&MessageBody=$util.base64Encode($input.json('$'))
    EOT
  }
}

resource "aws_api_gateway_method_response" "submit_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.submit.id
  http_method = aws_api_gateway_method.submit_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "submit_post_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.submit.id
  http_method = aws_api_gateway_method.submit_post.http_method
  status_code = aws_api_gateway_method_response.submit_post_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }

  response_templates = {
    "application/json" = <<-EOT
      #set($origin = $input.params("Origin"))
      #set($allowed = ${jsonencode(local.cors_allowed_origins)})
      #if($allowed.contains($origin))
        #set($context.responseOverride.header.Access-Control-Allow-Origin = $origin)
      #end
      #set($ctx.responseOverride.status = 202)
      {"status":"accepted","message":"Job submitted"}
    EOT
  }
}

resource "aws_api_gateway_method" "submit_options" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.submit.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_method_response" "submit_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.submit.id
  http_method = aws_api_gateway_method.submit_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration" "submit_options" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.submit.id
  http_method = aws_api_gateway_method.submit_options.http_method
  type        = "MOCK"

  request_templates = { "application/json" = "{\"statusCode\":200}" }
}

resource "aws_api_gateway_integration_response" "submit_options_200" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.submit.id
  http_method = aws_api_gateway_method.submit_options.http_method
  status_code = aws_api_gateway_method_response.submit_options_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }

  response_templates = {
    "application/json" = <<-EOT
      #set($origin = $input.params("Origin"))
      #set($allowed = ${jsonencode(local.cors_allowed_origins)})
      #if($allowed.contains($origin))
        #set($context.responseOverride.header.Access-Control-Allow-Origin = $origin)
      #end
      {"statusCode":200}
    EOT
  }
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_integration.submit_post,
      aws_api_gateway_integration.submit_options,
      aws_api_gateway_integration_response.submit_post_200,
      aws_api_gateway_integration_response.submit_options_200,
      aws_api_gateway_method.submit_post,
      aws_api_gateway_method.submit_options,
      aws_api_gateway_method_response.submit_post_200,
      aws_api_gateway_method_response.submit_options_200,
      aws_api_gateway_resource.submit,
    ]))
  }

  lifecycle { create_before_destroy = true }
}

resource "aws_api_gateway_stage" "main" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  deployment_id = aws_api_gateway_deployment.main.id
  stage_name    = var.stage_name
}

locals {
  cors_allowed_origins = concat(var.allowed_origins, ["https://${aws_cloudfront_distribution.main.domain_name}"])

  content_type_map = {
    js    = "text/javascript"
    html  = "text/html"
    css   = "text/css"
    ico   = "image/vnd.microsoft.icon"
    txt   = "text/plain"
    json  = "application/json"
    svg   = "image/svg+xml"
    png   = "image/png"
    woff2 = "font/woff2"
    map   = "application/json"
  }
}

# S3 bucket for the static frontend
data "aws_s3_bucket" "static" {
  bucket = var.static_bucket_name
}

# CloudFront Origin Access Control
resource "aws_cloudfront_origin_access_control" "main" {
  name                              = "${var.api_name}-${var.stage_name}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Bucket policy allowing CloudFront OAC access
data "aws_iam_policy_document" "cloudfront_s3" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${data.aws_s3_bucket.static.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudfront" {
  bucket = data.aws_s3_bucket.static.id
  policy = data.aws_iam_policy_document.cloudfront_s3.json
}

resource "aws_s3_object" "frontend" {
  for_each = fileset("${path.module}/../frontend/dist", "**")

  bucket       = data.aws_s3_bucket.static.bucket
  key          = each.value
  source       = "${path.module}/../frontend/dist/${each.value}"
  content_type = lookup(local.content_type_map, reverse(split(".", each.value))[0], "text/html")
  etag         = filemd5("${path.module}/../frontend/dist/${each.value}")
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "main" {
  origin {
    domain_name              = data.aws_s3_bucket.static.bucket_regional_domain_name
    origin_id                = "s3-${var.static_bucket_name}"
    origin_access_control_id = aws_cloudfront_origin_access_control.main.id
  }

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "Static frontend for ${var.api_name}"
  default_root_object = "index.html"

  aliases = []

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-${var.static_bucket_name}"

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  price_class = "PriceClass_100"

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  tags = { Name = "${var.api_name}-${var.stage_name}" }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
