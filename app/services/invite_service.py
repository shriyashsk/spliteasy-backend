import sendgrid
from sendgrid.helpers.mail import Mail
from app.config import settings


def send_invite_email(to_email: str, inviter_name: str, group_name: str, token: str):
    invite_url = f"{settings.FRONTEND_URL}/invite/{token}"
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject=f"{inviter_name} invited you to '{group_name}' on SplitEasy",
        html_content=f"""
        <h2>You've been invited!</h2>
        <p>{inviter_name} has invited you to join the group <strong>{group_name}</strong> on SplitEasy.</p>
        <p><a href="{invite_url}" style="background:#22c55e;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Accept Invitation</a></p>
        <p>This link expires in 7 days.</p>
        """,
    )
    sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    sg.send(message)


def send_password_reset_email(to_email: str, token: str):
    reset_url = f"{settings.FRONTEND_URL}/reset-password/{token}"
    message = Mail(
        from_email=settings.FROM_EMAIL,
        to_emails=to_email,
        subject="Reset your SplitEasy password",
        html_content=f"""
        <h2>Password Reset</h2>
        <p>Click the link below to reset your password. This link expires in 1 hour.</p>
        <p><a href="{reset_url}" style="background:#22c55e;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">Reset Password</a></p>
        <p>If you didn't request this, ignore this email.</p>
        """,
    )
    sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
    sg.send(message)