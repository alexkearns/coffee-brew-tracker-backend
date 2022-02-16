import json
from aws_lambda_powertools import Tracer, Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()


@app.get("/coffee-bean")
@tracer.capture_method(capture_response=False)
def list_coffee_beans():
    return {
        "coffeeBeans": [
            {"name": "Brazil", "roaster": "Horsham Coffee Roasters"}
        ]
    }


@app.get("/coffee-bean/<bean_id>")
@tracer.capture_method(capture_response=False)
def get_coffee_bean(bean_id):
    return {
        "id": bean_id,
        "name": "Brazil",
        "roaster": "Horsham Coffee Roasters"
    }


@tracer.capture_lambda_handler(capture_response=False)
@logger.inject_lambda_context
def lambda_handler(event, context):
    return app.resolve(event, context)
