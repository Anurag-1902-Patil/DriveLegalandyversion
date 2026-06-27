import datetime
import random
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import jwt

# We fetch the configuration safely from your .env file
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
JWT_SECRET = os.getenv("JWT_SECRET", "fallback_secret_key_change_this")

OTP_EXPIRY_MINUTES = 5

# A simple, secure local memory dictionary to track active OTP codes
# Format: { "user@email.com": { "code": "123456", "expires_at": datetime } }
otp_store = {}

def generate_otp() -> str:
    """Generates a secure, random 6-digit numeric string."""
    return f"{random.randint(100000, 999999)}"

def send_otp_email(receiver_email: str, otp_code: str) -> bool:
    """Connects to Google's SMTP server using SSL to deliver the code."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "Your Secure Verification Code"

        # A clean, professional layout matching a premium application style
        body = f"""
        <html>
            <body style="font-family: sans-serif; padding: 20px; color: #1e1e1e; max-width: 500px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="font-size: 20px; font-weight: 600; margin-bottom: 16px;">Verification Code</h2>
                <p style="font-size: 14px; color: #4b5563; line-height: 1.5;">Use the verification code below to access your account. This code is temporary and will expire in {OTP_EXPIRY_MINUTES} minutes.</p>
                <div style="background-color: #f9fafb; padding: 16px; font-size: 28px; font-weight: bold; letter-spacing: 6px; text-align: center; border-radius: 6px; margin: 24px 0; border: 1px solid #f3f4f6; color: #111827;">
                    {otp_code}
                </div>
                <p style="font-size: 12px; color: #9ca3af;">If you did not make this request, you can safely disregard this message.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        # Securely login and transmit
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"SMTP Email Error: {e}")
        return False

def request_otp(email: str) -> dict:
    """Generates an OTP, saves it locally, and dispatches the email."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return {"status": "error", "message": "Backend SMTP credentials are not configured in .env"}

    email = email.strip().lower()
    code = generate_otp()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    
    # Save code to memory (overwrites any previous unexpired codes for this user)
    otp_store[email] = {
        "code": code,
        "expires_at": expiry
    }
    
    email_sent = send_otp_email(email, code)
    if email_sent:
        return {"status": "success", "message": "OTP code successfully sent to email."}
    else:
        return {"status": "error", "message": "Failed to send email. Check your backend logs or App Password."}

def verify_otp(email: str, user_code: str) -> dict:
    """Validates the user-submitted code and issues a secure JWT session token."""
    email = email.strip().lower()
    record = otp_store.get(email)
    
    if not record:
        return {"status": "error", "message": "No verification request found for this email address."}
    
    # Check if the code has timed out
    if datetime.datetime.utcnow() > record["expires_at"]:
        del otp_store[email]
        return {"status": "error", "message": "The verification code has expired. Please request a new one."}
        
    # Check if the code matches
    if record["code"] != user_code.strip():
        return {"status": "error", "message": "Incorrect verification code."}
        
    # Success: Clear the code from active memory so it can't be used twice
    del otp_store[email]
    
    # Issue a secure session token valid for 7 days
    session_payload = {
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(session_payload, JWT_SECRET, algorithm="HS256")
    
    return {"status": "success", "token": token}