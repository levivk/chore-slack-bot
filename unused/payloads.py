import json
from typing import Any

class Payloads():

    def __init__(self) -> None:
        # Get payloads from json files
        with open('payloads/what_do.json', 'r') as f:
            self.what_do_blocks : list[Any] = json.loads(f.read())['blocks']

    def get_what_do_blocks(self, name: str ='user') -> list[Any]:
        these_blocks = self.what_do_blocks.copy()
        these_blocks[0]['text']['text'] = these_blocks[0]['text']['text'].format(name=name)
        return these_blocks
