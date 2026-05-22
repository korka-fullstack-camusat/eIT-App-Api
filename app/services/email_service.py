import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from ..config import settings


def send_otp_email(to_email: str, otp: str, username: str = "") -> None:
    if not settings.smtp_user or not settings.smtp_password:
        # Mode développement : afficher le code dans les logs
        print(f"[DEV] OTP pour {to_email} : {otp}")
        return

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:32px;
                background:#f6f8fa;border-radius:12px;">
      <img src="https://www.camusat.com/wp-content/uploads/2021/10/logo-camusat.png"
           alt="Camusat" style="height:48px;margin-bottom:24px;" />
      <h2 style="color:#003c71;margin-bottom:8px;">Réinitialisation de mot de passe</h2>
      <p style="color:#555;margin-bottom:24px;">
        Bonjour{' ' + username if username else ''},<br/>
        Voici votre code de vérification pour réinitialiser votre mot de passe :
      </p>
      <div style="background:#003c71;color:white;font-size:32px;font-weight:bold;
                  letter-spacing:10px;text-align:center;padding:20px;border-radius:8px;
                  margin-bottom:24px;">
        {otp}
      </div>
      <p style="color:#888;font-size:12px;">
        Ce code est valide pendant <strong>10 minutes</strong>.<br/>
        Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
      </p>
      <hr style="border:none;border-top:1px solid #ddd;margin:24px 0;" />
      <p style="color:#aaa;font-size:11px;text-align:center;">
        Camusat Sénégal — Direction IT
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Code de réinitialisation — Parc IT Camusat"
    msg["From"]    = settings.smtp_from
    msg["To"]      = to_email
    msg.attach(MIMEText(f"Votre code OTP : {otp}  (valide 10 min)", "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
