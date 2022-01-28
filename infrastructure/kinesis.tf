resource "aws_kinesis_firehose_delivery_stream" "extended_s3_stream" {
  name = "clickstream"
  destination = "extended_s3"
  
  extended_s3_configuration {
    role_arn   = aws_iam_role.datalake_role.arn
    bucket_arn = aws_s3_bucket.datalake_raw.arn 
    prefix = "clickstream/userId=!{partitionKeyFromQuery:userId}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "clickstream-errors/"
    buffer_size = 64
    buffer_interval = 60
    cloudwatch_logging_options {
      enabled = "true"
      log_group_name = aws_cloudwatch_log_group.clickstream_firehose.name
      log_stream_name = aws_cloudwatch_log_stream.clickstream_firehose.name
    }

    dynamic_partitioning_configuration {
      enabled = "true"
    }

    processing_configuration {
      enabled = "true"

      processors {
        type = "MetadataExtraction"

        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{userId:.user_id}"
        }
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
      }
      
      processors {
        type = "RecordDeAggregation"

        parameters {
          parameter_name  = "SubRecordType"
          parameter_value = "JSON"
        }
      }

      processors {
        type = "AppendDelimiterToRecord"

        parameters {
          parameter_name = "Delimiter"
          parameter_value = "\\n"
        }
      }
    }
  }
}

