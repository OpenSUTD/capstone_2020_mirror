import time
import os
import logging
import boto3

ssm = boto3.client("ssm")
logger = logging.getLogger()
logger.setLevel(os.environ["LOG_LEVEL"])


def lambda_handler(event, context):
    command_id = event["command_id"]
    response = ssm.list_commands(CommandId=command_id)
    return response["Commands"][0]["Status"]
