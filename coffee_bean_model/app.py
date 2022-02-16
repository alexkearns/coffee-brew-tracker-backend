import json


def lambda_handler(event, context):
    response = {}

    return {
        "statusCode": 200,
        "body": json.dumps(response),
    }
