variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "queue_name" {
  description = "Name of the SQS queue for job submissions"
  type        = string
  default     = "article-audio-jobs"
}

variable "api_name" {
  description = "Name of the API Gateway REST API"
  type        = string
  default     = "article-audio-api"
}

variable "stage_name" {
  description = "API Gateway deployment stage"
  type        = string
  default     = "dev"
}

variable "allowed_origins" {
  description = "Allowed origins for Cognito redirect URIs (list of URLs)"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "static_bucket_name" {
  description = "Name of the S3 bucket serving the static frontend"
  type        = string
  default     = "mungewrath-article-narrator-static"
}
