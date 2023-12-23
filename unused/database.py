
from enum import Flag, auto
import dataclasses as dc
import datetime
from slack_sdk import WebClient
import os
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

# What's a database??
# Using csv files is good enough for the scope of this project

# Assumptions
# - plain text names are unique
# - simultaneous file access will not happen and can be safely ignored

CHORE_COMPLETION_FILE = 'data/chore_completion.csv'
CHORE_ASSIGNMENT_FILE = 'data/chore_assignments.csv'
# CHORE_REMINDED_FILE = 'data/chore_reminded.csv'
KITCHEN_CLEANING_COMPLETION_FILE = 'data/kitchen_cleaning_completion.csv'
# KITCHEN_CLEANING_REMINDED_FILE = 'data/kitchen_cleaning_reminded.csv'
KITCHEN_ASSIGNMENT_FILE = 'data/kitchen_assignments.csv'

SLACK_USER_FILE = (Path(__file__).parent / "../data/users.csv").resolve()
# SLACK_USER_MEMBERS = [('name', str), ('slack_id', str), ('roles', Flag)]
# SLACK_USER_FILE_HEADERS = [i[0] for i in SLACK_USER_MEMBERS]
# SLACK_USER_ROLES = ['admin', 'manager', 'resident', 'chore-doer']

DELIMITER = ','
FLAG_DELIMITER = '|'
# silence reminders?
# Remember temporary swaps? - in completion file
# date overrides? - in completion files
# remember who has been reminded? - see logs
# use flags in completion files. text seperated by | parsed into enums?

class DatabaseFileError(Exception):
    pass

class DatabaseSlackClientError(Exception):
    pass

# https://stackoverflow.com/questions/6760685/creating-a-singleton-in-python
class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]



class UserTable(metaclass=Singleton):

    # Enum to handle roles
    class Role(Flag):
        ADMIN = auto()
        MANAGER = auto()
        RESIDENT = auto()
        CHOREDOER = auto()


    # TODO: low priority: reorg so there is one definition of column order
    @dc.dataclass(frozen=True)
    class User:
        name: str
        slack_id: str
        roles: Flag

    client: WebClient
    user_dict: dict[str, User]

    def __init__(self):
        self.client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

        # Get users from file
        with open(SLACK_USER_FILE, 'r') as f:
            rows = [l.strip().split(DELIMITER) for l in f.readlines()]

        user_file_headers = [f.name for f in dc.fields(self.User)]
        if rows[0][:3] != user_file_headers:
            logger.error(f'Slack user file contains invalid headers: {rows[0]}')
            raise DatabaseFileError('Slack user file contains incorrect headers!')

        # Create users
        self.user_dict = dict()
        for r in rows[1:]:
            try:
                name, slack_id, role_str = r[:3]        # NOTE: redef of column order
            except ValueError:
                logger.warning(f'Error unpacking row in user file: {r}')
                # Continue to next row
                continue

            roles = self.Role(0)
            for r in role_str.split('|'):
                if r == '' or r.isspace():
                    continue
                try:
                    roles |= self.Role[r.upper()]
                except KeyError:
                    logger.error(f'Invalid role in user file: {r}')
                    continue
            # Save to dict
            self.user_dict[name] = self.User(name, slack_id, roles)

        # print(self.user_dict.values())
        self.update_from_slack()
        self.write_to_file()

    def update_from_slack(self):
        # Request user info
        # members = []
        response = self.client.users_list()
        members: list|None = response['members']
        if members == None:
            logger.error('Could not update user list from Slack!')
            return

        existing_ids = [u.slack_id for u in self.user_dict.values()]
        for m in members:

            # Ignore users that are deleted or a bot or already in the "database"
            deleted = m['deleted']
            bot = m['is_bot']
            uid = m['id']
            if deleted or bot or uid in existing_ids:
                continue

            # add to list
            real_name = m.get('real_name', '')
            if real_name in self.user_dict:
                logger.warning(f'User {real_name} already exists with different UID!')
                continue
            # It is expected the admin may have to manually set roles and fix name if necessary for new residents
            roles = self.Role.RESIDENT      # Assume resident
            # Add to dict
            self.user_dict[real_name] = self.User(real_name, uid, roles)

        # for m in members:
        #     print(f"{m['name']: <20} {m['id']: <12} {m.get('real_name', ''): <20} {m['profile']['display_name']: <20} {m['deleted']: <10}")

    def write_to_file(self):
        
        # Open file and write header
        with open(SLACK_USER_FILE, 'w') as f:
            fields = dc.fields(self.User)
            for fi in fields:
                f.write(fi.name + DELIMITER)
            f.write('\n')

            # Loop through users and write each line
            for u in self.user_dict.values():
                f.write(u.name + DELIMITER + u.slack_id + DELIMITER)
                for r in self.Role:
                    if r in u.roles and r.name is not None:
                        f.write(r.name + FLAG_DELIMITER)
                f.write('\n')

    def __getitem__(self, name: str) -> User:
        return self.user_dict[name]

    def get_users_by_role(self, role: Role) -> list[User]:
        return [user for user in self.user_dict.values() if role in user.roles]



class KitchenAssignmentsTable(metaclass=Singleton):

    @dc.dataclass(frozen=True)
    class Assignment:
        name: str
        date: int
        swap_date: datetime.date|None

    assignments: list[Assignment]
    name_dict: dict[str,Assignment]
    date_dict: dict[int,Assignment]

    def __init__(self):

        #Get assignments from file
        with open(KITCHEN_ASSIGNMENT_FILE, 'r') as f:
            rows = [l.strip().split(DELIMITER) for l in f.readlines()]

        headers = [f.name for f in dc.fields(self.Assignment)]
        num_columns = len(headers)
        if rows[0][:num_columns] != headers:
            logger.error(f'Slack kitchen assignments file contains invalid headers: {rows[0]}')
            raise DatabaseFileError('Slack kitchen assignments file contains incorrect headers!')

        # Create assignments
        self.assignments = []
        self.name_dict = dict()
        self.date_dict = dict()
        for r in rows[1:]:
            try:
                name, date, swap = r[:num_columns]        # NOTE: redef of column order
            except ValueError:
                logger.warning(f'Invalid row in kitchen assignments file: {r}')
                # Continue to next row
                continue

            try:
                date = int(date)
            except ValueError:
                logger.error(f'Unable to convert date {date} to integer in kitchen assignments file')
                print(f'Unable to convert date {date} to integer')
                continue

            try:
                year, month, day = swap.split('/')
                year = int(year)
                month = int(month)
                day = int(day)
            except ValueError:
                swap_date = None
            else:
                swap_date = datetime.date(year, month, day)

            a = self.Assignment(name, date, swap_date)
            self.assignments.append(a)
            self.name_dict[name] = a
            # Make sure there isn't a duped date
            if date in self.date_dict:
                logger.warning(f'In kitchen assignments file, users {name} and {self.date_dict[date].name} have the same date!')
            else:
                self.date_dict[date] = a

        # print(self.assignments)

    def __getitem__(self, name: str) -> Assignment:
        return self.name_dict[name]

    def get_assignee_by_date(self, date: int) -> Assignment:
        # Get the assigned kitchen cleaner for the given day of the current month
        # Gives swap dates priority. Does not do any duplication checks or anything.
        # Raises keyerror if not assigned
        
        # Look through swaps first
        # make a date object for the day of month passed in
        today = datetime.date.today()
        target_date = today.replace(day=date)

        for a in self.assignments:
            if a.swap_date == target_date:
                return a

        # Not in a swap. Return normal assignee.
        return self.date_dict[date]


    def write_to_file(self):
        pass



if __name__ == '__main__':
    import os
    ut = UserTable()
    for u in ut.get_users_by_role(UserTable.Role.CHOREDOER):
        print(u.name)
    # kat = KitchenAssignmentsTable()
    # print(kat['Levi Vande Kamp'])
    # print(kat.get_assignee_by_date(4))