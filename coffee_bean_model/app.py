import boto3
import os
from botocore.exceptions import ClientError
from uuid import uuid4
from aws_lambda_powertools import Tracer, Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError
)

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("DYNAMODB_TABLE"))


def transform_coffee_bean_for_response(item):
    return {
        "id": item["PK"],
        "name": item["Name"],
        "strength": item["Strength"],
        "roaster": item["Roaster"],
        "tastingNotes": item["TastingNotes"]
    }


@app.get("/coffee-beans")
@tracer.capture_method(capture_response=False)
def list_coffee_beans():
    response = table.query(
        IndexName="GSI-SK",
        KeyConditionExpression="SK = :sk",
        ExpressionAttributeValues={
            ":sk": "BEAN#METADATA"
        }
    )

    items = response["Items"]
    transformed_items = list(map(transform_coffee_bean_for_response, items))
    return {
        "coffeeBeans": transformed_items
    }


@app.put("/coffee-beans/<bean_id>")
@tracer.capture_method(capture_response=False)
def update_coffee_bean(bean_id):
    json_payload = app.current_event.json_body
    if "name" not in json_payload:
        raise BadRequestError("name not included in request")

    table.update_item(
        Key={
            "PK": bean_id,
            "SK": "BEAN#METADATA"
        },
        UpdateExpression="SET #n = :name, Strength = :strength, Roaster = :roaster, TastingNotes = :tn",
        ExpressionAttributeNames={
            "#n": "Name"
        },
        ExpressionAttributeValues={
            ":name": json_payload["name"],
            ":strength": json_payload.get("strength", None),
            ":roaster": json_payload.get("roaster", None),
            ":tn": json_payload.get("tastingNotes", None)
        }
    )

    return {
        "message": f"{bean_id} has been successfully updated."
    }


@app.delete("/coffee-beans/<bean_id>")
@tracer.capture_method(capture_response=False)
def delete_coffee_bean(bean_id):
    try:
        table.delete_item(
            Key={
                "PK": bean_id,
                "SK": "BEAN#METADATA"
            },
            ConditionExpression="attribute_exists(#n)",
            ExpressionAttributeNames={
                "#n": "Name"
            }
        )
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Bean ID {bean_id} was not found")

    return {
        "message": f"{bean_id} has been successfully deleted."
    }


@app.get("/coffee-beans/<bean_id>")
@tracer.capture_method(capture_response=False)
def get_coffee_bean(bean_id):
    response = table.get_item(
        Key={
            "PK": bean_id,
            "SK": "BEAN#METADATA"
        }
    )

    if "Item" not in response:
        raise NotFoundError(f"Bean ID {bean_id} was not found")

    return transform_coffee_bean_for_response(response["Item"])


@app.post("/coffee-beans")
@tracer.capture_method(capture_response=False)
def add_coffee_bean():
    json_payload = app.current_event.json_body

    if "name" not in json_payload:
        raise BadRequestError("name not included in request")

    data_to_add = {
        "PK": str(uuid4()),
        "SK": "BEAN#METADATA",
        "Name": json_payload["name"],
        "Strength": json_payload.get("strength", None),
        "Roaster": json_payload.get("roaster", None),
        "TastingNotes": json_payload.get("tastingNotes", None)
    }

    table.put_item(
        Item=data_to_add
    )

    return {
        "message": f"{json_payload['name']} is added."
    }


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context
def lambda_handler(event, context):
    return app.resolve(event, context)
