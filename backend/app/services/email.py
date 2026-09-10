import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..core.config import settings


def enviar_correo(destinatarios: list[str], asunto: str, cuerpo_html: str, cuerpo_txt: str = "") -> None:
    if not settings.smtp_host or not settings.smtp_user:
        raise RuntimeError("SMTP no configurado")
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto
    if cuerpo_txt:
        msg.attach(MIMEText(cuerpo_txt, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    host = settings.smtp_host
    port = settings.smtp_port
    user = settings.smtp_user
    pwd = settings.smtp_pass
    use_tls = settings.smtp_tls
    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as s:
            if user:
                s.login(user, pwd)
            s.sendmail(msg["From"], destinatarios, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=10) as s:
            if use_tls:
                s.ehlo()
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
            if user:
                s.login(user, pwd)
            s.sendmail(msg["From"], destinatarios, msg.as_string())
