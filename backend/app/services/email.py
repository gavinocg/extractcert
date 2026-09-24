import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..db.database import SessionLocal
from .repo import smtp_settings


def enviar_correo(destinatarios: list[str], asunto: str, cuerpo_html: str, cuerpo_txt: str = "") -> None:
    db = SessionLocal()
    try:
        config = smtp_settings(db)
    finally:
        db.close()
    enviar_correo_config(config, destinatarios, asunto, cuerpo_html, cuerpo_txt)


def enviar_correo_config(config: dict, destinatarios: list[str], asunto: str, cuerpo_html: str, cuerpo_txt: str = "") -> None:
    if not config["host"] or not config["user"]:
        raise RuntimeError("SMTP no configurado")
    msg = MIMEMultipart("alternative")
    msg["From"] = config["from_email"] or config["user"]
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto
    if cuerpo_txt:
        msg.attach(MIMEText(cuerpo_txt, "plain", "utf-8"))
    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    host = config["host"]
    port = config["port"]
    user = config["user"]
    pwd = config["password"]
    use_tls = config["tls"]
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
