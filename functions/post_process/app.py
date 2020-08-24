import boto3
import json
import os
import time
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(os.environ["LOG_LEVEL"])
ssm = boto3.client("ssm")
PLAYBOOKS_BUCKET_NAME = os.environ["PLAYBOOKS_BUCKET_NAME"]
RUN_COMMAND_LOG_GROUP_NAME = os.environ["RUN_COMMAND_LOG_GROUP_NAME"]
MAIN_S3_BUCKET_NAME = os.environ["MAIN_S3_BUCKET_NAME"]
VERSIONS_BUCKET_NAME = os.environ["VERSIONS_BUCKET_NAME"]
MIRROR_TARGET = os.environ["MIRROR_TARGET"]
STACK_NAME = os.environ["STACK_NAME"]


def lambda_handler(event, context):
    instance_id = event["instance_id"]

    datestring = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-ApplyAnsiblePlaybooks",
        TimeoutSeconds=9001,
        Parameters={
            "SourceType": ["S3"],
            "SourceInfo": [
                json.dumps(
                    {
                        "path": f"https://s3.amazonaws.com/{PLAYBOOKS_BUCKET_NAME}/post_process"
                    }
                )
            ],
            "InstallDependencies": ["True"],
            "PlaybookFile": ["playbook.yml"],
            "Check": ["False"],
            "Verbose": ["-vvv"],
            "ExtraVariables": [
                f"main_s3_bucket={MAIN_S3_BUCKET_NAME} mirror_target={MIRROR_TARGET} ansible_python_interpreter=/usr/bin/python3 version_s3_bucket={VERSIONS_BUCKET_NAME} datestring={datestring}"
            ],
        },
        CloudWatchOutputConfig={
            "CloudWatchLogGroupName": RUN_COMMAND_LOG_GROUP_NAME,
            "CloudWatchOutputEnabled": True,
        },
    )
    command_id = response["Command"]["CommandId"]
    return {"status": "ok", "datestring": datestring, "command_id": command_id}
