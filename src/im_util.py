
import slack_send as ss
from storage import get_user_table
from slack_bolt.context.say.say import Say
from typing import Callable


def handle_command(command_text: str, say: Say) -> None:
    command_map: dict[str, Callable[[list[str]], str]] = {
        'testmode' : cmd_testmode,
        'user': cmd_user,
        'msg': cmd_msg,
    }

    help_text = "Available commands: {}".format(", ".join(command_map.keys()))

    cmds = command_text.lower().split()

    try:
        ret = command_map[cmds[0]](cmds[1:])
        say(ret)
    except KeyError:
        say(help_text)


def cmd_testmode(args: list[str]) -> str:
    help_text = "testmode {on|off}"

    if not args:
        return help_text
    
    mode = args[0].lower()

    if mode == "on":
        ss.set_test_mode(True)
    elif mode == "off":
        ss.set_test_mode(False)
    else:
        return help_text

    return f"Test mode set to {mode}"


def cmd_user(args: list[str]) -> str:
    help_text = "user {list}"

    if not args:
        return help_text

    arg = args[0].lower()

    if arg == "list":
        ret = ""
        for i,u in enumerate(get_user_table()):
            ret += f"{i}: {u.name}\n"
        return ret
    else:
        return help_text

# TODO: implement
def cmd_msg(args: list[str]) -> str:
    help_text = "msg {user_index} {message}"

    if not args:
        return help_text

    return help_text

