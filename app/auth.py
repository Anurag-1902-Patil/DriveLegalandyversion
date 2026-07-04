import datetime
import random
import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional # Added missing type hint token import here
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import UserDB

load_dotenv()

# Logger configuration
logger = logging.getLogger("drivelegal.auth")

# Fetch configurations safely from environmental variables
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "465").strip())
SENDER_EMAIL = (os.getenv("SENDER_EMAIL") or "").strip()
SMTP_USERNAME = (os.getenv("SMTP_USERNAME") or SENDER_EMAIL).strip()
SENDER_PASSWORD = (os.getenv("SENDER_PASSWORD") or "").replace(" ", "").strip()
JWT_SECRET = os.getenv("JWT_SECRET", "fallback_secret_key_change_this").strip()

OTP_EXPIRY_MINUTES = 5

# Initialize FastAPI Router for authentication
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Local volatile memory tracking active OTP maps
# Format: { "user@email.com": { "code": "123456", "expires_at": datetime } }
otp_store = {}

# ── Pydantic Request Schemas ──
class EmailPayload(BaseModel):
    email: EmailStr

class VerifyPayload(BaseModel):
    email: EmailStr
    code: str

# ── Core Utility Logic ──

def generate_otp() -> str:
    """Generates a secure, random 6-digit numeric string."""
    return f"{random.randint(100000, 999999)}"

def send_otp_email(receiver_email: str, otp_code: str) -> bool:
    """Connects to the configured SMTP server using SSL to deliver the code."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "Your Secure Verification Code"

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

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.login(SMTP_USERNAME, SENDER_PASSWORD)
            server.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            "SMTP authentication failed for %s via %s:%s. Gmail requires a valid app password for this account. Error: %s",
            SMTP_USERNAME,
            SMTP_SERVER,
            SMTP_PORT,
            e,
        )
        return False
    except Exception as e:
        logger.error(f"SMTP Email Error: {e}")
        return False

def decode_access_token(token: str) -> Optional[dict]:
    """
    Decodes an incoming JWT bearer token string.
    Returns the parsed session payload dictionary if valid, or None if expired/corrupted.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Incoming authentication token validation rejected: Signature Expired.")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Incoming authentication token validation rejected: Token Structure Broken.")
        return None

# ── FastAPI Routes ──

@router.post("/send-otp")
async def request_otp_endpoint(payload: EmailPayload):
    """API Endpoint: Generates an OTP, saves it locally, and dispatches the email."""
    if not SENDER_EMAIL or not SMTP_USERNAME or not SENDER_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backend SMTP credentials are not configured in .env."
        )

    email = payload.email.strip().lower()
    code = generate_otp()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=OTP_EXPIRY_MINUTES)
    
    otp_store[email] = {
        "code": code,
        "expires_at": expiry
    }
    
    email_sent = send_otp_email(email, code)
    if email_sent:
        logger.info(f"OTP successfully transmitted to: {email}")
        return {"status": "success", "message": "OTP code successfully sent to email."}

    del otp_store[email]
    
    logger.error("OTP delivery failed for %s.", email)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Failed to send OTP email. Check the sender Gmail app password and restart the backend."
    )

@router.post("/verify-otp")
async def verify_otp_endpoint(payload: VerifyPayload, db: Session = Depends(get_db)):
    """API Endpoint: Validates code, registers user on demand, and returns secure JWT."""
    email = payload.email.strip().lower()
    user_code = payload.code.strip()
    
    record = otp_store.get(email)
    
    if not record:
        raise HTTPException(status_code=400, detail="No verification request found for this email address.")
    
    if datetime.datetime.utcnow() > record["expires_at"]:
        del otp_store[email]
        raise HTTPException(status_code=401, detail="The verification code has expired. Please request a new one.")
        
    if record["code"] != user_code:
        raise HTTPException(status_code=401, detail="Incorrect verification code.")
        
    # Clear the verified OTP code out of local temporary storage
    del otp_store[email]
    
    # Check if user already exists in the SQLite persistent database
    user = db.query(UserDB).filter(UserDB.email == email).first()

    if not user:
        # Create a persistent entry for first-time login
        logger.info(f"New driver detected. Registering: {email}")
        user = UserDB(email=email, is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user) # Extracts the generated unique user.id integer
    else:
        logger.info(f"Returning user session loaded: {email}")
        
    # Issue secure payload with permanent database user_id attached
    session_payload = {
        "email": email,
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(session_payload, JWT_SECRET, algorithm="HS256")
    
    return {
        "status": "success", 
        "token": token, 
        "is_verified": user.is_verified,
        "user_id": user.id
    }
