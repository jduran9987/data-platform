resource "aws_cloudwatch_log_group" "clickstream_firehose" {
  name = "/aws/kinesisfirehose/clickstream"
}

resource "aws_cloudwatch_log_stream" "clickstream_firehose" {
  name           = "ClickStreamLogStream"
  log_group_name = aws_cloudwatch_log_group.clickstream_firehose.name
}

