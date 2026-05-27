output "api_endpoint" {
  description = "API Gateway endpoint URL for the submit endpoint"
  value       = "${aws_api_gateway_stage.main.invoke_url}/submit"
}

output "queue_url" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.jobs.url
}

output "queue_arn" {
  description = "SQS queue ARN"
  value       = aws_sqs_queue.jobs.arn
}

output "cognito_domain" {
  description = "Cognito Hosted UI domain"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "cognito_client_id" {
  description = "Cognito app client ID for the frontend"
  value       = aws_cognito_user_pool_client.frontend.id
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.main.id
}
