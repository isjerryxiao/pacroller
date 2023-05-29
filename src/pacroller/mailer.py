import json
import smtplib
from email.message import EmailMessage
from typing import List
import logging
import urllib.request, urllib.parse
from platform import node
from pacroller.config import NETWORK_RETRY, SMTP_ENABLED, SMTP_SSL, SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_TO, SMTP_AUTH, TG_ENABLED, TG_BOT_TOKEN, TG_API_HOST, TG_RECIPIENT, DEF_HTTP_HDRS

logger = logging.getLogger()
hostname = node() or "unknown-host"


def send_email(text: str, subject: str, mailto: List[str]) -> bool:
    for _ in range(NETWORK_RETRY):
        try:
            smtp_cls = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
            server = smtp_cls(SMTP_HOST, SMTP_PORT)
            if SMTP_AUTH:
                server.login(SMTP_AUTH["username"], SMTP_AUTH["password"])
            msg = EmailMessage()
            msg.set_content(f"from pacroller running on {hostname=}:\n\n{text}")
            msg['Subject'] = subject
            msg['From'] = SMTP_FROM
            msg['To'] = ', '.join(mailto)
            server.send_message(msg)
            server.quit()
        except Exception:
            logger.exception("error while send_email")
        else:
            logger.debug(f"smtp sent {text=}")
            break
    else:
        logger.error(f"unable to send email after {NETWORK_RETRY} attempts {text=}")
        return False
    return True


def send_tg_message(text: str, subject: str, mailto: List[str]) -> bool:
    for _ in range(NETWORK_RETRY):
        all_succeeded = True
        try:
            for recipient in mailto:
                url = f'https://{TG_API_HOST}/bot{TG_BOT_TOKEN}/sendMessage'
                headers = {'Content-Type': 'application/json'}
                data = json.dumps({"chat_id": recipient, "text": f"<b>{subject}</b>\n\n<code>{text[:4000]}</code>", "parse_mode": "HTML"})
                req = urllib.request.Request(url, data=data.encode('utf-8'), headers={**DEF_HTTP_HDRS, **headers})
                resp = urllib.request.urlopen(req).read().decode('utf-8')
                content = json.loads(resp)
                if not content.get("ok"):
                    all_succeeded = False
                    logger.error(f"unable to send telegram message to {recipient}: {content.get('description')}")
        except Exception:
            logger.exception("error while send_tg_message")
        else:
            logger.debug(f"telegram message sent {text=}")
            break
    else:
        logger.error(f"unable to send telegram message after {NETWORK_RETRY} attempts {text=}")
        return False
    return all_succeeded


class MailSender:
    def __init__(self) -> None:
        pass
    def send_text_plain(elsf, text: str, subject: str = f"pacroller on {hostname}") -> bool:
        if_failed = False
        if SMTP_ENABLED:
            if not send_email(text, subject, SMTP_TO.split()):
                if_failed = True
        if TG_ENABLED:
            if not send_tg_message(text, subject, TG_RECIPIENT.split()):
                if_failed = True
        if not SMTP_ENABLED and not TG_ENABLED:
            return None
        return not if_failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(module)s - %(funcName)s - %(levelname)s - %(message)s')
    print(MailSender().send_text_plain("This is a test mail\nIf you see this mail, your notification config is working."))
