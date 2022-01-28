resource "aws_iam_role" "datalake_role" {
  name = "datalake_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = [
            "s3.amazonaws.com",
            "firehose.amazonaws.com"
          ]
        }
      },
    ]
  })
}

resource "aws_iam_policy" "read_write_datalake_raw" {
  name = "read_write_datalake_raw"

  policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
        {
        "Effect": "Allow",
        "Action": ["s3:ListBucket"],
        "Resource": ["arn:aws:s3:::${aws_s3_bucket.datalake_raw.bucket}"]
        },
        {
        "Effect": "Allow",
        "Action": [
            "s3:PutObject",
            "s3:GetObject"
        ],
        "Resource": ["arn:aws:s3:::${aws_s3_bucket.datalake_raw.bucket}/*"]
        }
    ]
  })
}

resource "aws_iam_policy" "read_write_datalake_staging" {
  name = "read_write_datalake_staging"

  policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
        {
        "Effect": "Allow",
        "Action": ["s3:ListBucket"],
        "Resource": ["arn:aws:s3:::${aws_s3_bucket.datalake_staging.bucket}"]
        },
        {
        "Effect": "Allow",
        "Action": [
            "s3:PutObject",
            "s3:GetObject"
        ],
        "Resource": ["arn:aws:s3:::${aws_s3_bucket.datalake_staging.bucket}/*"]
        }
    ]
  })
}

resource "aws_iam_policy" "clickstream_cloudwatch" {
  name = "clickstream_cloudwatch"

  policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ],
        "Resource": "arn:aws:logs:us-east-1:${data.aws_caller_identity.current.account_id}:log-group:${aws_cloudwatch_log_group.clickstream_firehose.name}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "datalake_raw_attach" {
  role       = aws_iam_role.datalake_role.name
  policy_arn = aws_iam_policy.read_write_datalake_raw.arn
}

resource "aws_iam_role_policy_attachment" "datalake_staging_attach" {
  role       = aws_iam_role.datalake_role.name
  policy_arn = aws_iam_policy.read_write_datalake_staging.arn
}

resource "aws_iam_role_policy_attachment" "clickstream_cloudwatch_attach" {
  role       = aws_iam_role.datalake_role.name
  policy_arn = aws_iam_policy.clickstream_cloudwatch.arn
}

