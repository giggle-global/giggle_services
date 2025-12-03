# Email Notification Diagnostics Guide

## Common Issues and Solutions

### Issue 1: Email Notifications Not Enabled by Default
**Problem**: Users need to explicitly enable email notifications in their settings.

**Solution**: The code now defaults to `True` if not set, but existing users may have it set to `False`.

**Fix**: 
1. Check user settings in database
2. Update users to enable email notifications by default
3. Or update the code to always send emails regardless of preference (for critical notifications)

### Issue 2: SMTP Configuration Missing or Incorrect
**Problem**: SMTP credentials are not configured or incorrect.

**Check**:
```bash
# Check environment variables
echo $SMTP_SERVER
echo $SMTP_PORT
echo $SMTP_USERNAME
echo $SMTP_PASSWORD
echo $SMTP_FROM_EMAIL
```

**Fix**: Set all required SMTP environment variables.

### Issue 3: Email Service Errors Being Silently Swallowed
**Problem**: Errors are logged but not visible.

**Check Server Logs**:
```bash
# Look for email-related errors
grep -i "email\|smtp\|notification" app.log
```

**Solution**: Improved logging is now in place. Check logs for:
- `❌ Email configuration error`
- `❌ Failed to send notification email`
- `✅ Notification email sent successfully`

### Issue 4: User Email Address Missing
**Problem**: Users don't have email addresses in their profile.

**Check**: Verify users have email addresses in database.

### Issue 5: Gmail App Password Required
**Problem**: If using Gmail, you need an App Password, not your regular password.

**Fix**: 
1. Go to Google Account → Security
2. Enable 2-Step Verification
3. Generate App Password
4. Use the App Password in `SMTP_PASSWORD`

## Testing Email Configuration

### Test Email Service Directly
Create a test script `test_email.py`:

```python
from app.core.email_service import EmailService

email_service = EmailService()
try:
    email_service.send_notification_email(
        to_email="your-test@email.com",
        subject="Test Email",
        message="This is a test email from Giggle"
    )
    print("✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Check Notification Service Logs
Look for these log messages:
- `Sending notification email to...` - Email attempt started
- `✅ Notification email sent successfully` - Email sent
- `❌ Email configuration error` - Configuration issue
- `❌ Failed to send notification email` - Sending failed

## Quick Fixes

### Enable Email Notifications for All Users (Database Update)
```javascript
// MongoDB query to enable email notifications for all users
db.users.updateMany(
  {},
  { $set: { "notification_service.email": true } }
)
```

### Check Current Email Configuration
```python
from app.core.config import config
from app.core.email_service import EmailService

print("Email Provider:", config.get("email_provider"))
print("SMTP Server:", config.get("smtp_server"))
print("SMTP Username:", config.get("smtp_username"))
print("SMTP From:", config.get("smtp_from_email"))

# Test email service initialization
email_service = EmailService()
print("Email Service Provider:", email_service.provider)
```

## Environment Variables Required

```bash
# For SMTP (Gmail example)
EMAIL_PROVIDER=smtp
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # NOT your regular password!
SMTP_FROM_EMAIL=your-email@gmail.com

# For AWS SES
EMAIL_PROVIDER=ses
AWS_ACCESS_KEY=your-access-key
AWS_SECRET_KEY=your-secret-key
AWS_REGION=us-east-1
SES_FROM_EMAIL=verified-email@yourdomain.com
```

