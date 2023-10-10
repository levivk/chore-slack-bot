
from storage import user_table, UserRole
import config
from slack_sdk import WebClient
import logging


class AdminLogHandler(logging.Handler):

    wc: WebClient

    def __init__(self) -> None:
        super().__init__()
        self.wc = WebClient(token=config.get_slack_bot_token())

    def emit(self, record: logging.LogRecord) -> None:
        admins = tuple(u for u in user_table if UserRole.ADMIN in u.roles)
        for a in admins:
            try:
                self.wc.chat_postMessage(channel=a.slack_id, msg=self.format(record))
            except Exception:
                # nothing we can do
                pass
