data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "datalake_raw" {
  bucket = "${data.aws_caller_identity.current.account_id}-datalake-raw"
  acl    = "private"
}

resource "aws_s3_bucket" "datalake_staging" {
  bucket = "${data.aws_caller_identity.current.account_id}-datalake-staging"
  acl    = "private"
}

