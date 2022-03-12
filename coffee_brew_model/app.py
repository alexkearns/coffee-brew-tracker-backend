import boto3
import os
from urllib.parse import unquote
from botocore.exceptions import ClientError
from datetime import datetime
from aws_lambda_powertools import Tracer, Logger
from aws_lambda_powertools.event_handler.api_gateway import APIGatewayRestResolver, CORSConfig
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError
)

tracer = Tracer()
logger = Logger()
cors_config = CORSConfig(allow_origin="http://localhost:3001")
app = APIGatewayRestResolver(cors=cors_config)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv("DYNAMODB_TABLE"))


def transform_coffee_brew_for_response(item):
    return {
        "beanId": item["PK"],
        "time": item["SK"][5:],  # don't want the BREW# at the start
        "grindSize": item["GrindSize"],
        "waterTemperature": item["WaterTemperature"],
        "extractionTime": item["ExtractionTime"],
        "dose": item["Dose"],
        "yield": item["Yield"],
        "rating": item["Rating"],
        "comment": item["Comment"],
    }


@app.get("/coffee-beans/<bean_id>/brews")
@tracer.capture_method(capture_response=False)
def list_coffee_brews(bean_id):
    response = table.query(
        KeyConditionExpression="PK = :pk AND begins_with(SK, :sk)",
        ExpressionAttributeValues={
            ":pk": bean_id,
            ":sk": "BREW#"
        }
    )

    items = response["Items"]
    transformed_items = list(map(transform_coffee_brew_for_response, items))
    return {
        "coffeeBrews": transformed_items
    }


@app.put("/coffee-beans/<bean_id>/brews/<brew_time>")
@tracer.capture_method(capture_response=False)
def update_coffee_bean(bean_id, brew_time):
    json_payload = app.current_event.json_body

    table.update_item(
        Key={
            "PK": bean_id,
            "SK": f"BREW#{brew_time}"
        },
        UpdateExpression="""SET
            GrindSize = :gs, 
            Dose = :d, 
            Yield = :y, 
            ExtractionTime = :et, 
            WaterTemperature = :wt, 
            Rating = :r, 
            #C = :c 
        """,
        ExpressionAttributeNames={
            "#C": "Comment"
        },
        ExpressionAttributeValues={
            ":gs": json_payload.get("grindSize", None),
            ":d": json_payload.get("dose", None),
            ":y": json_payload.get("yield", None),
            ":et": json_payload.get("extractionTime", None),
            ":wt": json_payload.get("waterTemperature", None),
            ":r": json_payload.get("rating", None),
            ":c": json_payload.get("comment", None)
        }
    )

    return {
        "message": f"Brew at {brew_time} for bean {bean_id} has been successfully updated."
    }


@app.delete("/coffee-beans/<bean_id>/brews/<brew_time>")
@tracer.capture_method(capture_response=False)
def delete_coffee_brew(bean_id, brew_time):
    try:
        table.delete_item(
            Key={
                "PK": bean_id,
                "SK": f"BREW#{brew_time}"
            },
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames={
                "#pk": "PK"
            }
        )
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise NotFoundError(f"Brew at {brew_time} for Bean {bean_id} was not found")

    return {
        "message": f"Deletion successful."
    }


@app.get("/coffee-beans/<bean_id>/brews/<brew_time>")
@tracer.capture_method(capture_response=False)
def get_coffee_brew(bean_id, brew_time):
    response = table.get_item(
        Key={
            "PK": bean_id,
            "SK": f"BREW#{brew_time}"
        }
    )

    if "Item" not in response:
        raise NotFoundError(f"Brew for bean {bean_id} was not found")

    return transform_coffee_brew_for_response(response["Item"])


@app.post("/coffee-beans/<bean_id>/brews")
@tracer.capture_method(capture_response=False)
def add_coffee_brew(bean_id):
    json_payload = app.current_event.json_body
    date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    data_to_add = {
        "PK": bean_id,
        "SK": f"BREW#{date}",
        "GrindSize": json_payload.get("grindSize", None),
        "WaterTemperature": json_payload.get("waterTemperature", None),
        "Dose": json_payload.get("dose", None),
        "Yield": json_payload.get("yield", None),
        "ExtractionTime": json_payload.get("extractionTime", None),
        "Comment": json_payload.get("comment", None),
        "Rating": json_payload.get("rating", None)
    }

    table.put_item(
        Item=data_to_add
    )

    return {
        "message": f"Brew has been added."
    }


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context
def lambda_handler(event, context):
    return app.resolve(event, context)
