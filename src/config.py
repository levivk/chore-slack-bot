"""Module to handle environment variables"""

import os
from enum import StrEnum


class ConfigVars(StrEnum):
    SLACK_SS = "SLACK_SIGNING_SECRET"
    SLACK_BT = "SLACK_BOT_TOKEN"


def check_env_vars() -> None:
    """Check that the necessary environment variables are set"""
    missing = []
    for k in ConfigVars:
        v = os.environ.get(k)
        if v is None:
            missing.append(k)
    # Print out what is missing
    if missing:
        m = "\n".join(missing)
        raise ValueError(f"The following environment variables need to be set:\n{m}")


def get_slack_signing_secret() -> str:
    return os.environ[ConfigVars.SLACK_SS]


def get_slack_bot_token() -> str:
    return os.environ[ConfigVars.SLACK_BT]


def test() -> None:
    check_env_vars()
    print(f"slack ss: {get_slack_signing_secret()}")
    print(f"slack bt: {get_slack_bot_token()}")


if __name__ == "__main__":
    test()
