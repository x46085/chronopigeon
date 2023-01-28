#!/usr/bin/env python3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from natural.phone import e164
import time
import os
from datetime import datetime, timezone
import random

from concurrent import futures
import smtplib
import ptvsd
import grpc
import jinja2
import requests

from google.protobuf.json_format import MessageToJson
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from chronopigeon import api_pb2, api_pb2_grpc

import tasks
from logger import logger

ONE_DAY_IN_SECONDS = 24 * 60 * 60

TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates")

class Chronopigeon(api_pb2_grpc.ChronopigeonServiceServicer):
    def __init__(self):
        self.smtp_host = os.environ.get('SMTP_HOST')
        self.smtp_port = os.environ.get('SMTP_PORT')
        self.smtp_username = os.environ.get('SMTP_USERNAME')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        self.smtp_enable_ssl = bool(os.environ.get('SMTP_SSL') == 'True')
        self.domain = os.environ.get('SMTP_MAIL_DOMAIN')
        self.twilio_account_id = os.environ.get('KEYS_TWILIO_ACCOUNT_ID')
        self.twilio_api_key = os.environ.get('KEYS_TWILIO_API_KEY')
        self.twilio_msg_service_id = os.environ.get('KEYS_MESSAGING_SERVICE_ID')
        self.twilio_url = f'{os.environ.get("KEYS_TWILIO_URL")}/{self.twilio_account_id}/Messages.json'
        self.firebase_url = "https://fcm.googleapis.com/fcm/send"
        self.firebase_key = os.environ.get('KEYS_FIREBASE_AUTH_KEY')
        print(f'SMTP SSL Enabled: {self.smtp_enable_ssl}')

    # Begin Class helper functions:
    def template_fields_to_dict(self, template_data):
        data_dict = dict()

        if template_data is not True:
            for (field_name, field_value) in template_data.ListFields():
                name = field_name.name
                data = field_value
                data_dict[name] = data

        return data_dict

    def generate_boundary(self):
        chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        chars += '0123459789_'
        boundary = ''
        for _ in range(50):
            boundary += random.choice(chars)  # #nosec
        if '_' not in boundary:
            boundary = self.generate_boundary()
        return boundary

    def render_template(self, template_file, template_data):
        template_loader = jinja2.FileSystemLoader(searchpath=TEMPLATE_FOLDER)
        template_env = jinja2.Environment(
            loader=template_loader,
            undefined=jinja2.StrictUndefined,
            autoescape=True
        )

        template = template_env.get_template(template_file)

        return template.render(template_data)

    def render_text(self, template, template_data):
        template_file = "{}.txt.j2".format(template)

        return self.render_template(template_file, template_data)

    def render_html(self, template, template_data):
        template_file = "{}.html.j2".format(template)

        return self.render_template(template_file, template_data)

    def get_smtp_server(self):
        host = self.smtp_host
        port = self.smtp_port
        password = self.smtp_password
        user = self.smtp_username
        use_ssl = self.smtp_enable_ssl

        log_message = f'Connecting to {host}:{port}'
        logger.info(log_message)
        if use_ssl:
            smtp_server = smtplib.SMTP_SSL(host, port)
        else:
            smtp_server = smtplib.SMTP(host, port)

        # Optional login for the receiving mail_server. The "is not None"
        # logic allows for empty passwords ie. ""
        # We use an or here in case credentials are not properly provided.
        if user != "" or password != "":
            logger.info("Logging in to smtp server with username & password")
            try:
                smtp_server.login(user, password)
            except (smtplib.SMTPAuthenticationError, smtplib.SMTPException):
                msg = f'Failed to authenticate to {host}.'
                if user == "":
                    msg += " Username is empty."
                if password == "":
                    msg += " Password is empty."
                logger.critical(msg)
        else:
            logger.warning("No login credential provided. Assuming not needed.")

        # Dump communication with the receiving server straight to to the
        # console.
        if os.environ.get('LOGLEVEL') == "DEBUG":
            smtp_server.set_debuglevel(True)

        return smtp_server

    # Begin RPC Functions:

    def SendEmail(self, request, context):
        message = MIMEMultipart("alternative")
        message["Subject"] = request.subject
        boundary = self.generate_boundary()
        message.set_boundary(boundary)
        message_id = make_msgid(domain=self.domain)
        message.add_header('Message-ID', message_id)

        # for r in request.to_addresses:
        #     printf(r)
        if self.smtp_host == "email-smtp.us-west-2.amazonaws.com":
            request.bcc_addresses.append(api_pb2.EmailMap(display_name="developer@DOMAIN", email_address="developer@DOMAIN", fingerprint=""))
        message["To"] = ", ".join([r.email_address for r in request.to_addresses])
        message["Cc"] = ", ".join([r.email_address for r in request.cc_addresses])
        message["Bcc"] = ", ".join([r.email_address for r in request.bcc_addresses])
        message["From"] = request.from_address.email_address

        # Protobuf message type to dict conversion
        template_type = request.WhichOneof("template_data")
        template_name = EMAIL_TEMPLATES.get(template_type)
        if template_name is None:
            error_message = f'Unknown template: {template_type}'
            logger.critical(error_message)
            context.set_details(error_message)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return api_pb2.SendEmailResponse(
                send_successful=True,
                message="Email sent",
                message_id=message_id)
        field_dict = self.template_fields_to_dict(
            getattr(request, template_type)
        )
        # Set base items for template rendering that are computed from other
        # values
        field_dict['SUBJECT'] = request.subject
        field_dict['TEST_ID'] = request.test_id
        field_dict['CURRENT_YEAR'] = datetime.now().year

        # Turn these into plain/html MIMEText objects
        try:
            plain_part = MIMEText(self.render_text(template_name, field_dict), "plain")
            html_part = MIMEText(self.render_html(template_name, field_dict), "html")
        except Exception as error:  # pylint:disable=broad-except
            error_message = f'Template rendering error: {error}'
            logger.critical(error_message)
            context.set_details(error_message)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return api_pb2.SendEmailResponse()

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        message.attach(plain_part)
        message.attach(html_part)

        with self.get_smtp_server() as smtp_server:
            try:
                smtp_server.send_message(message)
            except Exception as error:  # pylint:disable=broad-except
                error_message = f'Email delivery failed: {error}'
                logger.critical(error_message)
                context.set_details(error_message)
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                return api_pb2.SendEmailResponse()
            else:
                info_message = f'Email delivery completed. Email sent to: {message["To"]}'
                logger.info(info_message)
                return api_pb2.SendEmailResponse(
                    send_successful=True,
                    message="Email sent",
                    message_id=message_id
                )

    def send_firebase_push_notification(self, collection, category, background, transaction_id, app_token, is_sender,
                                        is_finalized, success):
        json_obj = {
            "data": {
                "transaction_id": transaction_id,
                "collection": collection,
                "category": category,
                "is_sender": is_sender,
                "is_finalized": is_finalized,
                "success": success,
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            },
            "to": app_token
        }
        if background is not None:
            json_obj['notification'] = {
                "title": background.title,
                "body": background.body,
                "click_action": "FLUTTER_NOTIFICATION_CLICK",
            }

        headers = {
            "content-type": "application/json",
            "authorization": "key=" + self.firebase_key
        }
        response = requests.post(self.firebase_url, json=json_obj, headers=headers)
        response.raise_for_status()
        return response.status_code

    def validate_firebase_token(self, app_token):
        url = f"{self.firebase_url}?dry_run=true"
        json_obj = {
            "registration_ids": [app_token],
        }
        headers = {
            "content-type": "application/json",
            "authorization": "key=" + self.firebase_key
        }
        response = requests.post(url, json=json_obj, headers=headers)
        response.raise_for_status()
        return response.json()["success"] > 0

    def SendPushNotification(self, request, context):
        status_code = self.send_firebase_push_notification(
            request.collection,
            request.category,
            request.background,
            request.transaction_id,
            request.notification_token,
            request.is_sender,
            request.is_finalized,
            request.success,
        )
        return api_pb2.SendPushNotifyResponse(response_code=status_code)

    def SendSMS(self, request, context):
        data = {
            'MessagingServiceSid': self.twilio_msg_service_id,
            # https://www.twilio.com/docs/sms/send-messages#to
            'To': e164(request.phone_number),
            'Body': request.sms_message
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(self.twilio_url, auth=(self.twilio_account_id, self.twilio_api_key), data=data,
                                 headers=headers)
        response.raise_for_status()
        return api_pb2.SendSMSResponse(response_code=response.status_code)

    def ValidatePushNotificationSettings(self, request, context):
        is_valid = self.validate_firebase_token(request.notification_token)
        return api_pb2.ValidationResponse(is_valid=is_valid)

    def ScheduleTask(self, request, context):
        logger.info('Schedule task request received')

        # Request task must be specified for it to be handled correctly
        if request.task == api_pb2.ScheduleTaskRequest.UNKNOWN:  # pylint: disable=no-member
            context.set_details('Task must be provided')
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return api_pb2.ScheduleTaskResponse()

        # If an execution time is specified in UTC timestamp convert it to
        # a datetime object with a UTC timezone
        execute_at = None
        if request.execute_at:
            execute_at = datetime.utcfromtimestamp(request.execute_at)
            execute_at = execute_at.replace(tzinfo=timezone.utc)

        # Schedule email requests
        if request.task == api_pb2.ScheduleTaskRequest.SEND_EMAIL:  # pylint: disable=no-member
            # Make email_request into json so it can be serialized onto queue
            log_msg = f'Send email request: {request.email_request.subject}'
            logger.info(log_msg)
            email_request = MessageToJson(request.email_request)

            # Confirm whether the task should be run asap or scheduled for a
            # different time
            utc_datetime_now = datetime.utcnow().replace(tzinfo=timezone.utc)
            logger.info('Queueing task')
            if execute_at is None or utc_datetime_now > execute_at:
                queued_task = tasks.send_email.delay(email_request)
                log_msg = f'{queued_task.id} - Send Email task queued to run as soon as possible'
                logger.info(log_msg)
            else:
                queued_task = tasks.send_email.apply_async(args=[email_request], eta=execute_at)
                log_msg = f'{queued_task.id} - Send Email task scheduled to execute at: {execute_at}, time now: {utc_datetime_now}'
                logger.info(log_msg)

            return api_pb2.ScheduleTaskResponse(success=True, task_id=queued_task.id)

        if request.task == api_pb2.ScheduleTaskRequest.SEND_SMS:
            logger.info(f'Scheduling SMS: {request.sms_request.phone_number}')
            sms_request = MessageToJson(request.sms_request)

            utc_datetime_now = datetime.utcnow().replace(tzinfo=timezone.utc)

            if execute_at is None or utc_datetime_now > execute_at:
                queued_task = tasks.send_sms.delay(sms_request)
                logger.info(f'{queued_task.id} - Send SMS task queued to run asap')
            else:
                queued_task = tasks.send_sms.apply_async(args=[sms_request], eta=execute_at)
                logger.info(('{task_id} - Send SMS task scheduled to ' +
                             'execute at: {eta}, time now: {now}').format(
                    task_id=queued_task.id,
                    eta=execute_at,
                    now=utc_datetime_now
                ))

            return api_pb2.ScheduleTaskResponse(
                success=True,
                task_id=queued_task.id
            )

    def CancelTask(self, request, context):
        logger.info('Cancel task request received')
        logger.info(request)

        if request.task_id is None:
            context.set_details("Task ID must be provided")
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return api_pb2.CancelTaskResponse()

        # Revoking a task cancels it
        tasks.app.control.revoke(request.task_id)

        return api_pb2.CancelTaskResponse(success=True)


EMAIL_TEMPLATES = {
    "GenericMessage": "generic_message",
    "generic_message": "generic_message",
    "EmailVerification": "email_verification",
    "email_verification": "email_verification",
    "RequestNotification": "request_notification",
    "request_notification": "request_notification",
    "TransactionNotification": "transaction_notification",
    "transaction_notification": "transaction_notification",
    "UserInfoUpdateNotification": "user_info_update_notification",
    "user_info_update_notification": "user_info_update_notification",
    "AccountRecoveredNotification": "account_recovered_notification",
    "account_recovered_notification": "account_recovered_notification",
    "RecoveryCodeNotification": "recovery_code_notification",
    "recovery_code_notification": "recovery_code_notification",
    "ApplicationSubmissionNotification": "application_submission",
    "application_submission_notification": "application_submission",
    "ApplicationVerifiedNotification": "application_verified",
    "application_verified_notification": "application_verified",
    "ApplicationDeniedNotification": "application_denied",
    "application_denied_notification": "application_denied",
    "DocumentSubmissionNotification": "document_submission",
    "document_submission_notification": "document_submission",
    "DocumentFailedNotification": "document_failed",
    "document_failed_notification": "document_failed",
    "DocumentVerifiedNotification": "document_verified",
    "document_verified_notification": "document_verified",
    "GenericDiaPayNotification": "generic_dia_pay",
    "generic_dia_pay_notification": "generic_dia_pay",
    "WireTransferDiaPayNotification": "wire_transfer_dia_pay",
    "wire_transfer_dia_pay_notification": "wire_transfer_dia_pay",
    "business_onboarding_dia_pay_notification": "business_onboarding_dia_pay",
    "withdrawal_dia_pay_notification": "withdrawal_dia_pay",
    "ApplicationSubmissionDiaPayNotification": "application_submission_dia_pay",
    "application_submission_dia_pay_notification": "application_submission_dia_pay",
    "ApplicationVerifiedDiaPayNotification": "application_verified_dia_pay",
    "application_verified_dia_pay_notification": "application_verified_dia_pay",
    "ApplicationDeniedDiaPayNotification": "application_denied_dia_pay",
    "application_denied_dia_pay_notification": "application_denied_dia_pay",
    "DocumentSubmissionDiaPayNotification": "document_submission_dia_pay",
    "document_submission_dia_pay_notification": "document_submission_dia_pay",
    "DocumentFailedDiaPayNotification": "document_failed_dia_pay",
    "document_failed_dia_pay_notification": "document_failed_dia_pay",
    "DocumentVerifiedDiaPayNotification": "document_verified_dia_pay",
    "document_verified_dia_pay_notification": "document_verified_dia_pay",
}


def serve():
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    grpc_server.add_insecure_port('{host}:{port}'.format(host='0.0.0.0', port='50051'))

    health_servicer = health.HealthServicer()
    health_servicer.set('chronopigeon', health_pb2.HealthCheckResponse.SERVING)  # pylint: disable=no-member
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, grpc_server)
    api_pb2_grpc.add_ChronopigeonServiceServicer_to_server(Chronopigeon(), grpc_server)

    return grpc_server


if __name__ == "__main__":
    # ptvsd.enable_attach()
    server = serve()
    server.start()
    logger.info("GRPC server started.")

    try:
        while True:
            time.sleep(ONE_DAY_IN_SECONDS)
    finally:
        server.stop(0)
