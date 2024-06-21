
import storage as st
import config
from slack_sdk import WebClient
import logging


class AdminLogHandler(logging.Handler):

    wc: WebClient

    def __init__(self) -> None:
        super().__init__()
        self.wc = WebClient(token=config.get_slack_bot_token())

    def emit(self, record: logging.LogRecord) -> None:
        ut = st.get_user_table()
        admins = tuple(u for u in ut if st.UserRole.ADMIN in u.roles)
        for a in admins:
            try:
                self.wc.chat_postMessage(channel=a.slack_id, text=self.format(record))
            except Exception:
                print("failed to log to slack.")
                # nothing we can do
                pass
