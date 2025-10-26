from core.aws_utils import (
    publish_email_via_sns,
    send_email_via_ses,
    send_raw_email_via_ses,
    generate_s3_presigned_post,
    generate_s3_presigned_get_url,
    generate_s3_presigned_urls_for_object,
)

# SNS
publish_email_via_sns(
    topic_arn="arn:aws:sns:us-east-1:123456789012:my-topic",
    subject="Request accepted",
    message="Freelancer X accepted your request. Project ID: prj-123",
)

# SES simple
send_email_via_ses(
    source="no-reply@yourdomain.com",
    to_addresses=["user@example.com"],
    subject="Welcome",
    body_text="Text body",
    body_html="<p>HTML body</p>",
    region_name="us-east-1",
)

# SES raw with attachment
send_raw_email_via_ses(
    source="no-reply@yourdomain.com",
    to_addresses=["user@example.com"],
    subject="Invoice",
    body_text="Please find invoice attached",
    attachments={"invoice.pdf": open("invoice.pdf", "rb").read()},
)

# S3 presigned POST (for browser upload)
post = generate_s3_presigned_post(bucket="my-bucket", key="uploads/user-123/photo.png", expires_in=900)
# returns { "url": "https://...", "fields": {...} } which the frontend can use with formData

# S3 presigned GET for inline viewing
view_url = generate_s3_presigned_get_url(bucket="my-bucket", key="uploads/user-123/photo.png", inline=True, expires_in=3600)

# Both view and download URLs
urls = generate_s3_presigned_urls_for_object(bucket="my-bucket", key="reports/r1.pdf", expires_in=3600)
print(urls["view_url"], urls["download_url"])
