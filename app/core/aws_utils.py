# core/aws_utils.py
from typing import Optional, Dict, Any, Tuple
import logging
import time
import json
import email.mime.application
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import config

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# ----------------------
# Client factories (easy to mock in tests)
# ----------------------

def _sns_client(region_name: Optional[str] = None):
    """
    Create an SNS client using credentials from environment variables.
    Expected ENV vars:
      - AWS_ACCESS_KEY_ID
      - AWS_SECRET_ACCESS_KEY
      - AWS_REGION (optional)
    """
    return boto3.client(
        "sns",
        aws_access_key_id=config.get("aws_access_key"),
        aws_secret_access_key=config.get("aws_secret_key"),
        region_name=region_name or config.get("aws_region")
    )


def _ses_client(region_name: Optional[str] = None):
    """
    Create an SES client using environment-based credentials.
    """
    return boto3.client(
        "ses",
        aws_access_key_id=config.get("aws_access_key"),
        aws_secret_access_key=config.get("aws_secret_key"),
        region_name=region_name or config.get("aws_region")
    )


def _s3_client(region_name: Optional[str] = None):
    """
    Create an S3 client using environment-based credentials.
    """
    return boto3.client(
        "s3",
        aws_access_key_id=config.get("aws_access_key"),
        aws_secret_access_key=config.get("aws_secret_key"),
        region_name=region_name or config.get("aws_region")
    )


# ----------------------
# SNS: publish a subject+message to a Topic ARN (email subscribers must be subscribed)
# ----------------------
def publish_email_via_sns(
    topic_arn: str,
    subject: str,
    message: str,
    message_attributes: Optional[Dict[str, Dict[str, Any]]] = None,
    region_name: Optional[str] = None,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
    sns_client=None,
) -> Dict[str, Any]:
    """
    Publish a message to SNS topic. Email addresses must be subscribed to the topic.
    Returns boto3 publish response.
    """
    client = sns_client or _sns_client(region_name=region_name)
    attempt = 0
    while True:
        try:
            params = {"TopicArn": topic_arn, "Subject": subject, "Message": message}
            if message_attributes:
                params["MessageAttributes"] = message_attributes
            resp = client.publish(**params)
            logger.info("SNS publish successful: %s", resp.get("MessageId"))
            return resp
        except (BotoCoreError, ClientError) as exc:
            attempt += 1
            logger.exception("SNS publish failed attempt %d/%d", attempt, max_retries)
            if attempt >= max_retries:
                raise
            time.sleep(backoff_seconds * attempt)


# ----------------------
# SES: simple send_email (no attachments) using SendEmail API
# ----------------------
def send_email_via_ses(
    source: str,
    to_addresses: list,
    subject: str,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    cc_addresses: Optional[list] = None,
    bcc_addresses: Optional[list] = None,
    region_name: Optional[str] = None,
    ses_client=None,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
) -> Dict[str, Any]:
    """
    Send an email using SES SendEmail API (simple usage). `source` must be a verified identity
    if SES is in sandbox mode. Use `send_raw_email` below for attachments or custom headers.
    """
    client = ses_client or _ses_client(region_name=region_name)
    attempt = 0
    while True:
        try:
            destination = {"ToAddresses": to_addresses}
            if cc_addresses:
                destination["CcAddresses"] = cc_addresses
            if bcc_addresses:
                destination["BccAddresses"] = bcc_addresses

            message = {"Subject": {"Data": subject, "Charset": "utf-8"}}
            body = {}
            if body_text:
                body["Text"] = {"Data": body_text, "Charset": "utf-8"}
            if body_html:
                body["Html"] = {"Data": body_html, "Charset": "utf-8"}
            message["Body"] = body

            resp = client.send_email(Source=source, Destination=destination, Message=message)
            logger.info("SES send_email successful: %s", resp.get("MessageId"))
            return resp
        except (BotoCoreError, ClientError) as exc:
            attempt += 1
            logger.exception("SES send_email failed attempt %d/%d", attempt, max_retries)
            if attempt >= max_retries:
                raise
            time.sleep(backoff_seconds * attempt)


# ----------------------
# SES: send raw email (supports attachments)
# ----------------------
def send_raw_email_via_ses(
    source: str,
    to_addresses: list,
    subject: str,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    attachments: Optional[Dict[str, bytes]] = None,  # dict of filename -> bytes
    region_name: Optional[str] = None,
    ses_client=None,
    max_retries: int = 3,
    backoff_seconds: float = 0.5,
) -> Dict[str, Any]:
    """
    Build a MIME email and send using SES send_raw_email. Useful for attachments and custom headers.
    attachments: {"file.pdf": b'...', "image.png": b'...'}
    """
    client = ses_client or _ses_client(region_name=region_name)

    # Build MIME
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = source
    msg["To"] = ", ".join(to_addresses)

    if body_text:
        msg.attach(MIMEText(body_text, "plain", _charset="utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", _charset="utf-8"))

    if attachments:
        for fname, bdata in attachments.items():
            part = email.mime.application.MIMEApplication(bdata)
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)

    raw = msg.as_string().encode("utf-8")

    attempt = 0
    while True:
        try:
            resp = client.send_raw_email(Source=source, Destinations=to_addresses, RawMessage={"Data": raw})
            logger.info("SES send_raw_email successful: %s", resp.get("MessageId"))
            return resp
        except (BotoCoreError, ClientError) as exc:
            attempt += 1
            logger.exception("SES send_raw_email failed attempt %d/%d", attempt, max_retries)
            if attempt >= max_retries:
                raise
            time.sleep(backoff_seconds * attempt)


# ----------------------
# S3: presigned POST for browser uploads (returns url and fields)
# ----------------------
def generate_s3_presigned_post(
    bucket: str,
    key: str,
    expires_in: int = 3600,
    acl: Optional[str] = None,
    content_type_startswith: Optional[str] = None,
    region_name: Optional[str] = None,
    s3_client=None,
    extra_conditions: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Generate a presigned POST (form data + url) for direct browser uploads.
    Returns dict: {"url": "...", "fields": {...}}
    Example usage in browser: fetch(url, { method: 'POST', body: formData })
    """
    client = s3_client or _s3_client(region_name=region_name)

    fields = {"key": key}
    if acl:
        fields["acl"] = acl

    conditions = [{"key": key}]
    if acl:
        conditions.append({"acl": acl})
    if content_type_startswith:
        # allows client to set Content-Type that startswith provided value
        conditions.append(["starts-with", "$Content-Type", content_type_startswith])

    if extra_conditions:
        conditions.extend(extra_conditions)

    try:
        resp = client.generate_presigned_post(Bucket=bucket, Key=key, Fields=fields, Conditions=conditions, ExpiresIn=expires_in)
        # resp has {"url": "...", "fields": {...}}
        return resp
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Failed to generate presigned POST for s3://%s/%s", bucket, key)
        raise


# ----------------------
# S3: presigned GET (view inline) and presigned GET (download attachment)
# ----------------------
def generate_s3_presigned_get_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
    region_name: Optional[str] = None,
    s3_client=None,
    inline: bool = True,
    response_content_type: Optional[str] = None,
) -> str:
    """
    Generate a presigned GET URL for viewing/downloading an object.
    If inline=True, adds header to hint inline viewing (Content-Disposition: inline).
    If inline=False, adds header to force download (Content-Disposition: attachment; filename="keyname").
    Optionally set response_content_type to hint browser.
    """
    client = s3_client or _s3_client(region_name=region_name)

    params = {"Bucket": bucket, "Key": key}
    response_headers = {}
    if response_content_type:
        response_headers["ResponseContentType"] = response_content_type

    # Set Content-Disposition
    filename = key.split("/")[-1]
    if inline:
        response_headers["ResponseContentDisposition"] = f'inline; filename="{filename}"'
    else:
        response_headers["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

    if response_headers:
        params.update(response_headers)

    try:
        url = client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
        return url
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Failed to generate presigned GET URL for s3://%s/%s", bucket, key)
        raise


# ----------------------
# S3: convenience wrapper for download + view with explicit names
# ----------------------
def generate_s3_presigned_urls_for_object(
    bucket: str,
    key: str,
    expires_in: int = 3600,
    region_name: Optional[str] = None,
    s3_client=None,
    response_content_type: Optional[str] = None,
) -> Dict[str, str]:
    """
    Returns both 'view_url' (inline) and 'download_url' (attachment).
    """
    client = s3_client or _s3_client(region_name=region_name)
    view = generate_s3_presigned_get_url(bucket=bucket, key=key, expires_in=expires_in, region_name=region_name, s3_client=client, inline=True, response_content_type=response_content_type)
    download = generate_s3_presigned_get_url(bucket=bucket, key=key, expires_in=expires_in, region_name=region_name, s3_client=client, inline=False, response_content_type=response_content_type)
    return {"view_url": view, "download_url": download}
