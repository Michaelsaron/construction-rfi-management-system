import smtplib
from email.message import EmailMessage
from app.config import settings

def send_email(to:str,subject:str,body:str):
    if not settings.smtp_host or not settings.smtp_from:
        print(f'[EMAIL-DEV] To={to} Subject={subject}\n{body}')
        return
    msg=EmailMessage();msg['From']=settings.smtp_from;msg['To']=to;msg['Subject']=subject;msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=20) as s:
        if settings.smtp_tls:s.starttls()
        if settings.smtp_user:s.login(settings.smtp_user,settings.smtp_password or '')
        s.send_message(msg)
