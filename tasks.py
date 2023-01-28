import os
import grpc
from celery import Celery, exceptions
from celery.utils.log import get_task_logger
from google.protobuf import json_format

import celeryconfig

# Proto definitions
from chronopigeon import api_pb2, api_pb2_grpc

CHRONOPIGEON_HOST = os.environ.get('CHRONOPIGEON_SERVICE_HOST', 'localhost')
CHRONOPIGEON_PORT = os.environ.get('CHRONOPIGEON_SERVICE_PORT', 50051)
chronopigeon_channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')

app = Celery('tasks')
app.config_from_object(celeryconfig)
logger = get_task_logger(__name__)


# Default max_retries = 3, setting to None makes it infinite
# Retries up to 52 minutes from initial attempt
@app.task(name='tasks.send_email', bind=True, max_retries=5)
def send_email(self, email_request):
    task_id = self.request.id
    try:
        email_request = json_format.Parse(
            email_request, api_pb2.SendEmailRequest(),
            ignore_unknown_fields=False
        )
        stub = api_pb2_grpc.ChronopigeonServiceStub(chronopigeon_channel)
        email_response = stub.SendEmail(email_request)
        log_msg = f'{task_id} - Task processed: {email_response.send_successful}'
        logger.info(log_msg)
    except Exception as error:  # pylint:disable=broad-except
        log_msg = f'{task_id} - Task FAILED with error: {error}'
        logger.error(log_msg)

        try:
            # Countdown in seconds with exponential growth
            countdown = 5 ** self.request.retries
            self.retry(countdown=countdown)
        except exceptions.MaxRetriesExceededError:
            log_msg = f'{task_id} - MaxRetriesExceededError'
            logger.error(log_msg)

# Default max_retries = 3, setting to None makes it infinite
# Retries up to 52 minutes from initial attempt
@app.task(name='tasks.send_sms', bind=True, max_retries=5)
def send_sms(self, sms_request):
    task_id = self.request.id
    try:
        sms_request = json_format.Parse(
            sms_request, api_pb2.SendSMSRequest(),
            ignore_unknown_fields=False
        )
        stub = api_pb2_grpc.ChronopigeonServiceStub(chronopigeon_channel)
        sms_response = stub.SendSMS(sms_request)
        log_msg = f'{task_id} - Task processed: {sms_response.response_code}'
        logger.info(log_msg)
    except Exception as error:  # pylint:disable=broad-except
        log_msg = f'{task_id} - Task FAILED with error: {error}'
        logger.error(log_msg)

        try:
            # Countdown in seconds with exponential growth
            countdown = 5 ** self.request.retries
            self.retry(countdown=countdown)
        except exceptions.MaxRetriesExceededError:
            log_msg = f'{task_id} - MaxRetriesExceededError'
            logger.error(log_msg)
