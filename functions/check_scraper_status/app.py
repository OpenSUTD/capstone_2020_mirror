import time
import os
import logging
import boto3

ssm = boto3.client("ssm")
logger = logging.getLogger()
logger.setLevel(os.environ["LOG_LEVEL"])


class CommandRunError(Exception):
    pass


def lambda_handler(event, context):
    instance_id = event["instance_id"]
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        TimeoutSeconds=9001,
        Parameters={"commands": ["systemctl show httrack -p SubState"],},
    )
    command_id = response["Command"]["CommandId"]
    while True:
        response = ssm.list_commands(CommandId=command_id)
        if response["Commands"][0]["Status"] in ("InProgress", "Pending"):
            logger.debug("Command status is " + response["Commands"][0]["Status"])
            time.sleep(1)
        else:
            break

    if response["Commands"][0]["Status"] != "Success":
        logger.fatal("systemctl show status did not exit successfully")
        raise CommandRunError()

    r2 = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
    return r2["StandardOutputContent"].replace("SubState=", "").strip()
