import os
import unittest
import time
import uuid
from datetime import datetime, timezone
from random import randint

from celery import Celery
import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from chronopigeon import api_pb2, api_pb2_grpc

from server import serve
import celeryconfig

TO_EMAIL_ADDRESS = 'developer@DOMAIN'
TO_EMAIL_DISPLAY_NAME = 'Testy Mctesterson'
FROM_EMAIL_ADDRESS = 'developer@DOMAIN'
FROM_EMAIL_DISPLAY_NAME = 'Friendly Developer'
VERIFICATION_URL = 'https://app.DOMAIN/verify'
CHRONOPIGEON_HOST = os.environ.get('CHRONOPIGEON_SERVICE_HOST', 'localhost')
CHRONOPIGEON_PORT = os.environ.get('CHRONOPIGEON_SERVICE_PORT', 50051)
SERVER_RUNNING = os.environ.get('SERVER_RUNNING', 1)

app = Celery('tasks')
app.config_from_object(celeryconfig)


def create_email_verification_request(to_name=TO_EMAIL_DISPLAY_NAME, verification_url=VERIFICATION_URL):
    email_verification = api_pb2.EmailVerification(
        name=to_name,
        verification_url=verification_url
    )

    email_request = api_pb2.SendEmailRequest(
        from_address=api_pb2.EmailMap(
            display_name=FROM_EMAIL_DISPLAY_NAME,
            email_address=FROM_EMAIL_ADDRESS
        ),

        to_addresses=[api_pb2.EmailMap(
            display_name=to_name,
            email_address=TO_EMAIL_ADDRESS
        )],

        subject='Email Verification',
        email_verification=email_verification
    )

    return email_request


def create_user_update_email_request():
    user_info_update_notification = api_pb2.UserInfoUpdateNotification()

    email_request = api_pb2.SendEmailRequest(
        from_address=api_pb2.EmailMap(
            display_name=FROM_EMAIL_DISPLAY_NAME,
            email_address=FROM_EMAIL_ADDRESS
        ),

        to_addresses=[api_pb2.EmailMap(
            display_name=TO_EMAIL_DISPLAY_NAME,
            email_address=TO_EMAIL_ADDRESS
        )],

        subject='User Update',
        user_info_update_notification=user_info_update_notification
    )

    return email_request


def create_account_recovered_email_request():
    account_recovered_notification = api_pb2.AccountRecoveredNotification()

    email_request = api_pb2.SendEmailRequest(
        from_address=api_pb2.EmailMap(
            display_name=FROM_EMAIL_DISPLAY_NAME,
            email_address=FROM_EMAIL_ADDRESS
        ),

        to_addresses=[api_pb2.EmailMap(
            display_name=TO_EMAIL_DISPLAY_NAME,
            email_address=TO_EMAIL_ADDRESS
        )],

        subject='Account Recovered',
        account_recovered_notification=account_recovered_notification
    )

    return email_request


def create_recovery_code_email_request(code='111111'):
    recovery_code_notification = api_pb2.RecoveryCodeNotification(
        verification_code=code
    )

    email_request = api_pb2.SendEmailRequest(
        from_address=api_pb2.EmailMap(
            display_name=FROM_EMAIL_DISPLAY_NAME,
            email_address=FROM_EMAIL_ADDRESS
        ),

        to_addresses=[api_pb2.EmailMap(
            display_name=TO_EMAIL_DISPLAY_NAME,
            email_address=TO_EMAIL_ADDRESS
        )],

        subject='Recovery Code',
        recovery_code_notification=recovery_code_notification
    )

    return email_request


def create_money_request_email_request(name, amount, request_url):
    request_notification = api_pb2.RequestNotification(
        name=name,
        amount=amount,
        currency='USD',
        request_url=request_url
    )

    email_request = api_pb2.SendEmailRequest(
        from_address=api_pb2.EmailMap(
            display_name=FROM_EMAIL_DISPLAY_NAME,
            email_address=FROM_EMAIL_ADDRESS
        ),

        to_addresses=[api_pb2.EmailMap(
            display_name=TO_EMAIL_DISPLAY_NAME,
            email_address=TO_EMAIL_ADDRESS
        )],

        subject='Money Request',
        request_notification=request_notification
    )

    return email_request


class TestHealthCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = health_pb2_grpc.HealthStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_health_check(self):
        health_check_request = health_pb2.HealthCheckRequest(
            service='chronopigeon'
        )

        response = self.stub.Check(health_check_request)
        self.assertTrue(response.status == health_pb2.HealthCheckResponse.SERVING)  # pylint: disable=no-member


class TestVerifyEmail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_user_update_email(self):
        update_email = self.stub.SendEmail(create_user_update_email_request())
        self.assertTrue(update_email.send_successful)

    def test_account_recovered_email(self):
        account_recovered_email = self.stub.SendEmail(create_account_recovered_email_request())
        self.assertTrue(account_recovered_email.send_successful)

    def test_recovery_code_email(self):
        code = str(randint(100000, 999999))
        recovery_code_email = self.stub.SendEmail(create_recovery_code_email_request(code))
        self.assertTrue(recovery_code_email.send_successful)

    def test_money_request_email(self):
        amount = str(randint(100000, 999999))
        request_url = 'https://app.DOMAIN/request'
        request_email = self.stub.SendEmail(create_money_request_email_request("Calvin", amount, request_url))
        self.assertTrue(request_email.send_successful)

    def test_verification_email(self):
        name = TO_EMAIL_DISPLAY_NAME
        verification_url = 'https://app.DOMAIN/verify'

        verification_email = self.stub.SendEmail(create_email_verification_request(name, verification_url))
        self.assertTrue(verification_email.send_successful)


class TestSMS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

class TestPushNotification(unittest.TestCase):
    # Web push notification token by sadroeck
    REAL_FCM_APP_TOKEN = "ewrhocVgaOwFv3kqFHbcTe:APA91bGE8M_ZMTIRGKvp3J7ImAhUkbG5xU5lHBySKJHYhgiCD6UlGhlZ8" \
                         "pfP1q7rfTXmBNRYLItOIastDfrLrGKhZwQtAYTP0rUd7e8-jG1rQEiDv67HuD6BNmU-C_moPdO9W2F9aeXc"

    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)

    @classmethod
    def tearDownClass(cls):
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_app_token_validation(self):
        request = api_pb2.PushNotificationSettings(notification_token='fake_token')
        response = self.stub.ValidatePushNotificationSettings(request)
        self.assertFalse(response.is_valid, "fake_token is not a real firebase app token")

        request = api_pb2.PushNotificationSettings(notification_token=self.REAL_FCM_APP_TOKEN)
        response = self.stub.ValidatePushNotificationSettings(request)
        self.assertTrue(response.is_valid, "Expected a valid response for a real firebase app token")


class TestSMSTaskScheduling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)
        cls.queue_inspector = app.control.inspect()

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_schedule_sms_send_task(self):
        sms_request = api_pb2.SendSMSRequest(
            phone_number='1234567890',
            sms_message='ChronoPigeon Test Task Scheduled SMS'
        )

        utc_now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
        schedule_request = api_pb2.ScheduleTaskRequest(
            task=api_pb2.ScheduleTaskRequest.SEND_SMS,  # pylint: disable=no-member
            execute_at=round(utc_now + 2),
            sms_request=sms_request
        )

        response = self.stub.ScheduleTask(schedule_request)
        self.assertTrue(response.success)


class TestEmailTaskScheduling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)
        cls.queue_inspector = app.control.inspect()

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_schedule_email_send_task(self):
        unique_name = str(uuid.uuid4())
        unique_url = VERIFICATION_URL + str(uuid.uuid4())
        email_request = create_email_verification_request(unique_name, unique_url)

        utc_now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
        schedule_request = api_pb2.ScheduleTaskRequest(
            task=api_pb2.ScheduleTaskRequest.SEND_EMAIL,  # pylint: disable=no-member
            execute_at=round(utc_now + 2),
            email_request=email_request
        )

        response = self.stub.ScheduleTask(schedule_request)
        self.assertTrue(response.success)


class TestCancelTask(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SERVER_RUNNING == 0:
            cls.server = serve()
            cls.server.start()
        cls.channel = grpc.insecure_channel(f'{CHRONOPIGEON_HOST}:{CHRONOPIGEON_PORT}')
        cls.stub = api_pb2_grpc.ChronopigeonServiceStub(cls.channel)
        cls.queue_inspector = app.control.inspect()

    @classmethod
    def tearDownClass(cls):
        cls.channel.close()
        if SERVER_RUNNING == 0:
            cls.server.stop(0)

    def test_cancel_send_email_task(self):
        unique_name = str(uuid.uuid4())
        unique_url = str(uuid.uuid4())
        email_request = create_email_verification_request(unique_name, unique_url)

        utc_now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()
        schedule_request = api_pb2.ScheduleTaskRequest(
            task=api_pb2.ScheduleTaskRequest.SEND_EMAIL,  # pylint: disable=no-member
            execute_at=round(utc_now + 5),
            email_request=email_request
        )

        schedule_response = self.stub.ScheduleTask(schedule_request)
        self.assertTrue(schedule_response.success)

        # Make request to cancel task
        task_id = schedule_response.task_id
        cancel_request = api_pb2.CancelTaskRequest(
            task_id=task_id
        )
        cancel_response = self.stub.CancelTask(cancel_request)
        self.assertTrue(cancel_response.success)

        # Get revoke lists from workers
        revoked_lists = self.queue_inspector.revoked()
        self.assertTrue(revoked_lists)

        # Check that the task_id is in every worker revoke list
        for _, revoked_list in revoked_lists.items():
            self.assertTrue(revoked_list and task_id in revoked_list)
