"""Servicio de email para notificaciones transaccionales.

Si SMTP_HOST no está configurado, el mensaje se escribe en el log en lugar
de enviarse — útil para entornos de desarrollo o instancias auto-gestionadas.
"""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import (
    APP_BASE_URL,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger(__name__)


def _send_sync(to: str, subject: str, body_html: str, body_text: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to], msg.as_bytes())


async def send_email(to: str, subject: str, body_html: str, body_text: str) -> None:
    if not SMTP_HOST:
        logger.warning(
            "SMTP no configurado — email NO enviado a %s | Asunto: %s | Contenido: %s",
            to, subject, body_text,
        )
        return
    try:
        await asyncio.to_thread(_send_sync, to, subject, body_html, body_text)
        logger.info("Email enviado a %s | %s", to, subject)
    except Exception:
        logger.exception("Error enviando email a %s | %s", to, subject)


async def send_extraction_complete_email(to: str, document_name: str, status: str, extraction_id: str) -> None:
    icon = "✅" if status == "success" else "❌"
    label = "completada correctamente" if status == "success" else "fallida"
    subject = f"{icon} Extracción {label} — {document_name}"
    url = f"{APP_BASE_URL}/history"
    body_text = f"La extracción del documento '{document_name}' ha {label}.\nVer en: {url}"
    body_html = f"""<!DOCTYPE html><html lang="es"><body style="font-family:sans-serif;color:#1a1a2e;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#7c3aed">Centinell</h2>
  <p>{icon} La extracción de <strong>{document_name}</strong> ha {label}.</p>
  <p><a href="{url}" style="display:inline-block;background:#7c3aed;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">Ver historial</a></p>
  <p style="color:#999;font-size:0.75em">ID: {extraction_id}</p>
</body></html>"""
    await send_email(to, subject, body_html, body_text)


async def send_assessment_complete_email(to: str, assessment_name: str, document_name: str, status: str, run_id: str) -> None:
    icon = "✅" if status == "success" else "❌"
    label = "completado" if status == "success" else "fallido"
    subject = f"{icon} Assessment {label} — {assessment_name}"
    url = f"{APP_BASE_URL}/history"
    body_text = f"El assessment '{assessment_name}' sobre '{document_name}' ha {label}.\nVer en: {url}"
    body_html = f"""<!DOCTYPE html><html lang="es"><body style="font-family:sans-serif;color:#1a1a2e;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#7c3aed">Centinell</h2>
  <p>{icon} El assessment <strong>{assessment_name}</strong> sobre <strong>{document_name}</strong> ha {label}.</p>
  <p><a href="{url}" style="display:inline-block;background:#7c3aed;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">Ver historial</a></p>
  <p style="color:#999;font-size:0.75em">Run ID: {run_id}</p>
</body></html>"""
    await send_email(to, subject, body_html, body_text)


async def send_password_reset_email(to: str, token: str) -> None:
    reset_url = f"{APP_BASE_URL}/reset-password?token={token}"
    subject = "Recuperación de contraseña — Centinell"
    body_text = (
        f"Solicita restablecer tu contraseña en Centinell.\n\n"
        f"Usa este enlace (válido 60 minutos):\n{reset_url}\n\n"
        "Si no lo solicitaste, ignora este mensaje."
    )
    body_html = f"""
<!DOCTYPE html>
<html lang="es">
<body style="font-family:sans-serif;color:#1a1a2e;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#7c3aed">Centinell</h2>
  <p>Has solicitado restablecer tu contraseña.</p>
  <p>
    <a href="{reset_url}"
       style="display:inline-block;background:#7c3aed;color:#fff;
              padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600">
      Restablecer contraseña
    </a>
  </p>
  <p style="color:#666;font-size:0.85em">
    El enlace es válido durante <strong>60 minutos</strong>.<br>
    Si no solicitaste el cambio, ignora este mensaje.
  </p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
  <p style="color:#999;font-size:0.75em">Centinell Console</p>
</body>
</html>
"""
    await send_email(to, subject, body_html, body_text)
