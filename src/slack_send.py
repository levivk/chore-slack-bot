import config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from typing import Any
import logging

_logger = logging.getLogger(__name__)
_client = WebClient(token=config.get_slack_bot_token())

_test_mode = False

def get_test_mode() -> bool:
    return _test_mode

def set_test_mode(mode: bool) -> None:
    global _test_mode
    _test_mode = mode
    _logger.info("Test mode is {}".format("ENABLED" if _test_mode else "DISABLED"))

def get_user_display_name(slack_id: str) -> str:

    try:
        response = _client.users_info(user=slack_id)
    except SlackApiError as e:
        _logger.error(f'Error getting user display name: {str(e)}')
        return 'idk name'
    
    try:
        user: dict[str, Any] = response.get('user', {})
        if user == {}:
            raise ValueError
    except ValueError:
        _logger.error('Invalid response to slack user info request')
        return "idk name"
    
    try:
        disp_name: str = user['profile']['display_name']
    except KeyError:
        _logger.error('Invalid response to slack user info request')
        return 'idk name'

    return disp_name

def msg_user(slack_id: str, msg: str, ignore_test_mode:bool = False) -> None:
    _logger.info(f"id: {slack_id} name: {get_user_display_name(slack_id)} msg: {msg}")

    if (not _test_mode) or ignore_test_mode:
        _client.chat_postMessage(channel=slack_id, text=msg)
