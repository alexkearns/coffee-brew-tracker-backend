import boto3
import os
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
        "name": item["PK"],
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



@app.get("/coffee-beans/<bean_id>")
@tracer.capture_method(capture_response=False)
def get_coffee_bean(bean_id):
    return {
        "id": bean_id,
        "name": "Brazil",
        "roaster": "Horsham Coffee Roasters"
    }


@app.post("/coffee-beans")
@tracer.capture_method(capture_response=False)
def add_coffee_bean():
    json_payload = app.current_event.json_body

    if "name" not in json_payload:
        raise BadRequestError("name not included in request")

    data_to_add = {
        "PK": json_payload["name"],
        "SK": "BEAN#METADATA",
        "Strength": json_payload.get("strength", None),
        "Roaster": json_payload.get("roaster", None),
        "TastingNotes": json_payload.get("tastingNotes", None)
    }

    table.put_item(
        Item=data_to_add
    )

    return {
        "Message": f"{json_payload['name']} is added."
    }


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context
def lambda_handler(event, context):
    return app.resolve(event, context)
