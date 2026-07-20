from app.workers.celery_app import celery_app
from loguru import logger
from typing import Optional


@celery_app.task(bind=True, name="app.workers.tasks.send_email", max_retries=3)
def send_email(self, to_email: str, subject: str, html_body: str, from_email: Optional[str] = None):
    """Send an email via SendGrid."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        from app.core.config import settings

        message = Mail(
            from_email=from_email or settings.FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email}: status {response.status_code}")
        return {"status": "sent", "to": to_email, "code": response.status_code}
    except Exception as exc:
        logger.error(f"Email failed to {to_email}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, name="app.workers.tasks.send_sms", max_retries=3)
def send_sms(self, to_number: str, message: str):
    """Send SMS via Twilio."""
    try:
        from twilio.rest import Client
        from app.core.config import settings

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        result = client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to_number,
        )
        logger.info(f"SMS sent to {to_number}: {result.sid}")
        return {"status": "sent", "sid": result.sid}
    except Exception as exc:
        logger.error(f"SMS failed to {to_number}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(bind=True, name="app.workers.tasks.send_whatsapp", max_retries=3)
def send_whatsapp(self, to_number: str, message: str):
    """Send WhatsApp message via Meta Business API."""
    try:
        import httpx
        from app.core.config import settings

        headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message},
        }
        url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_ID}/messages"
        response = httpx.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"WhatsApp sent to {to_number}")
        return {"status": "sent", "to": to_number}
    except Exception as exc:
        logger.error(f"WhatsApp failed to {to_number}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.generate_report_pdf")
def generate_report_pdf(order_id: str) -> str:
    """Generate a PDF dispatch summary for an order."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        import io, base64

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("Western Haul Transport", styles["Title"]))
        elements.append(Paragraph("Dispatch Summary Report", styles["Heading2"]))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"Order ID: {order_id}", styles["Normal"]))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        return pdf_b64
    except Exception as exc:
        logger.error(f"PDF generation failed: {exc}")
        raise


@celery_app.task(name="app.workers.tasks.send_dispatch_notifications")
def send_dispatch_notifications(dispatch_id: str, order_number: str, driver_phone: str, customer_email: str):
    """Send dispatch notifications to driver and customer."""
    driver_msg = f"[Western Haul] Order {order_number} - You have been assigned a new dispatch. Please check your app."
    send_sms.delay(driver_phone, driver_msg)

    email_body = f"""
    <h2>Dispatch Confirmed</h2>
    <p>Your order <strong>{order_number}</strong> has been dispatched.</p>
    <p>You will receive live updates as your shipment progresses.</p>
    <p>Thank you for choosing Western Haul Transport.</p>
    """
    send_email.delay(customer_email, f"Order {order_number} Dispatched", email_body)
