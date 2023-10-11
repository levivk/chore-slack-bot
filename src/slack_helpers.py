import config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import Any
import logging
logger = logging.getLogger(__name__)

_client = WebClient(token=config.get_slack_bot_token())

def get_user_display_name(slack_id: str) -> str:

    try:
        response = _client.users_info(user=slack_id)
    except SlackApiError as e:
        logger.error(f'Error getting user display name: {str(e)}')
        return 'idk name'
    
    try:
        user: dict[str, Any] = response.get('user', {})
        if user == {}:
            raise ValueError
    except ValueError:
        logger.error('Invalid response to slack user info request')
        return "idk name"
    
    try:
        disp_name: str = user['profile']['display_name']
    except KeyError:
        logger.error('Invalid response to slack user info request')
        return 'idk name'

    return disp_name

def msg_user(slack_id: str, msg: str) -> None:
    _client.chat_postMessage(channel=slack_id, text=msg)
