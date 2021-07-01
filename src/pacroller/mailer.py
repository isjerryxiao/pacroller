import smtplib
from email.message import EmailMessage
from typing import List
import logging
from platform import node
from pacroller.config import NETWORK_RETRY, SMTP_ENABLED, SMTP_SSL, SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_TO, SMTP_AUTH

logger = logging.getLogger()
hostname = node() or "unknown-host"

class MailSender:
    def __init__(self) -> None:
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.ssl = SMTP_SSL
        self.auth = SMTP_AUTH
        self.mailfrom = SMTP_FROM
        self.mailto = SMTP_TO.split()
        self.smtp_cls = smtplib.SMTP_SSL if self.ssl else smtplib.SMTP
    def send_text_plain(self, text: str, subject: str = f"pacroller from {hostname}", mailto: List[str] = list()) -> None:
        if not SMTP_ENABLED:
            return
        for _ in range(NETWORK_RETRY):
            try:
                server = self.smtp_cls(self.host, self.port)
                if self.auth:
                    server.login(self.auth["username"], self.auth["password"])
                mailto = mailto if mailto else self.mailto
                msg = EmailMessage()
                msg.set_content(f"from pacroller running on {hostname=}:\n\n{text}")
                msg['Subject'] = subject
                msg['From'] = self.mailfrom
                msg['To'] = ', '.join(mailto)
                server.send_message(msg)
                server.quit()
            except Exception:
                logger.exception("error while smtp send_message")
            else:
                logger.debug(f"smtp sent {text=}")
                break
        else:
            logger.error(f"unable to send email after {NETWORK_RETRY} attempts {text=}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    MailSender().send_text_plain("This is a test mail\nIf you see this email, your smtp config is working.")
