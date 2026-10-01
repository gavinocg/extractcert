import smtplib
import socket
import ssl
from ipaddress import ip_address
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..db.database import SessionLocal
from .repo import smtp_settings


def validar_host_smtp(host: str, permitir_red_interna: bool = False) -> str:
    """Valida el host y todas sus resoluciones antes de abrir una conexion SMTP."""
    host = host.strip().rstrip(".").lower()
    try:
        literal = ip_address(host)
    except ValueError:
        literal = None
    if not host or len(host) > 253 or host == "localhost" or (literal is None and any(
        not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
        or not all(char.isalnum() or char == "-" for char in label)
        for label in host.split(".")
    )):
        raise ValueError("Host SMTP no valido")
    if literal is not None:
        addresses = {str(literal)}
    else:
        try:
            addresses = {item[4][0].split("%", 1)[0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}
        except socket.gaierror as exc:
            raise ValueError("Host SMTP no valido") from exc
    if not addresses:
        raise ValueError("Host SMTP no valido")
    if not permitir_red_interna:
        for address in addresses:
            ip = ip_address(address)
            if not ip.is_global:
                raise ValueError("Host SMTP no permitido")
    return host


def enviar_correo(destinatarios: list[str], asunto: str, cuerpo_html: str, cuerpo_txt: str = "") -> None:
    db = SessionLocal()
    try:
        config = smtp_settings(db)
    finally:
        db.close()
    # La configuracion persistida constituye la autorizacion explicita para hosts internos.
    config["permitir_red_interna"] = True
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
    host = validar_host_smtp(config["host"], bool(config.get("permitir_red_interna")))
    port = config["port"]
    user = config["user"]
    pwd = config["password"]
    use_tls = config["tls"]
    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=10) as s:
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
