
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from database import UserTable
import logging
logger = logging.getLogger(__name__)

class SlackDriver:

    client: WebClient
    ut: UserTable

    def __init__(self, token_env = 'SLACK_BOT_TOKEN'):

        self.client = WebClient(token=os.environ[token_env])
        self.ut = UserTable()

    def msg_user(self, user_name: str, msg: str, log_errors: bool = True):

        try:
            slack_id = self.ut[user_name].slack_id
        except KeyError:
            if log_errors: logger.error('Tried to message user that does not exist!')
            return

        try:
            self.client.chat_postMessage(
                channel=slack_id,
                text = msg,
            )
        except SlackApiError as e:
            if log_errors: logger.error(f'Error sending user message: {str(e)}')
            

    def get_user_display_name(self, user_name: str) -> str:

        slack_id = self.ut[user_name].slack_id
        try:
            response = self.client.users_info(user=slack_id)
        except SlackApiError as e:
            logger.error(f'Error getting user display name: {str(e)}')
            return ''
        
        try:
            user: dict|None = response['user']
            if user is None:
                logger.error('Invalid response to slack user info request')
                return ''

            disp_name = user['profile']['display_name']
        except KeyError:
            logger.error('Invalid response to slack user info request')
            return ''

        return disp_name


if __name__ == '__main__':
    sd = SlackDriver()
    sd.msg_user('Levi Vande Kamp', 'Hi Levi, from bot <3')