import config
import enum
from dataclasses import dataclass, fields
import datetime
from slack_sdk import WebClient
from typing import Any, Self, Iterable, Iterator, TypeVar, Generic, Optional
from abc import ABC, abstractmethod
from threading import Lock
import os
from pathlib import Path
import csv
import shutil
from io import TextIOWrapper
import logging

logger = logging.getLogger(__name__)


SLACK_USER_FILE = (Path(__file__).parent / "../data/users.csv").resolve()
KITCHEN_ASSIGNMENT_FILE = (Path(__file__).parent / "../data/kitchen_assignments.csv").resolve()


@dataclass
class TableRow(ABC):
    """
    Abstract class for table rows. Subclass with members for columns.
    Modifying members will write parent table to disk.
    """

    __slots__ = "_parent_table"

    def __post_init__(self) -> None:
        """
        Called by the dataclass __init__
        """
        self._parent_table: Optional["PersistentTable[Self]"] = None

    def __setattr__(self, name: str, value: Any) -> None:
        # don't lock if not part of dataclass
        if name not in [f.name for f in fields(self)]:
            object.__setattr__(self, name, value)
            return
        # Get lock, set, sync table
        with self.get_lock():
            object.__setattr__(self, name, value)
            self.sync()

    def set_parent_table(self, parent_table: Optional["PersistentTable[Self]"]) -> None:
        self._parent_table = parent_table

    def get_lock(self) -> Lock:
        """
        Get the Threading.Lock of the parent table. Member modification is already thread-safe.
        """
        if not hasattr(self, "_parent_table"):
            # we are in TableRow initialization which means row is not yet in table
            # and no need to lock
            return Lock()
        if self._parent_table is None:
            # parent table hasn't been set, but row is initialized. Error.
            raise ValueError("Cannot get lock. This row does not belong to a table.")
        # Get lock from table
        return self._parent_table.get_lock()

    def sync(self) -> None:
        """
        Write the parent table to disk. This is done automatically on member modification.
        """
        if not hasattr(self, "_parent_table"):
            # No table, no sync
            return
        if self._parent_table is None:
            # Initialized with no table, error
            raise ValueError("Cannot sync. This row does not belong to a table.")
        return self._parent_table.sync()

    @abstractmethod
    def as_dict(self) -> dict[str, str]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, member_dict: dict[str, str]) -> Self:
        raise NotImplementedError


TR = TypeVar("TR", bound=TableRow)


class PersistentTable(Generic[TR]):
    """
    Table-like object with write through csv file storage

    inspired by: https://code.activestate.com/recipes/576642/
    """

    def __init__(self, filename: str | Path, row_type: type[TR], create_new: bool = False):
        self.filename = filename
        self.items: list[TR] = list()
        self.row_type: type[TR] = row_type
        self.fieldnames = [f.name for f in fields(self.row_type)]

        # lock for thread safety
        self.lock = Lock()

        if not create_new and os.access(filename, os.R_OK):
            with open(filename, "r", newline="") as csvfile:
                self.load(csvfile)

    def load(self, csvfile: Iterable[str]) -> None:
        self.items.clear()
        print('loading csv')
        try:
            reader = csv.DictReader(csvfile)
            # convert each row to a table row
            for row in reader:
                print(f'row: {row}')
                self.append(self.row_type.from_dict(row))
        except Exception as e:
            raise ValueError(f"Data file {self.filename} not formatted correctly or something: {e}")

    def sync(self) -> None:
        """
        Open file and write items
        """
        tempname = str(self.filename) + ".tmp"
        with open(tempname, "w", newline="") as csvfile:
            try:
                self.dump(csvfile)
            except Exception:
                os.remove(tempname)
                raise
            shutil.move(tempname, self.filename)  # atomic

    def dump(self, csvfile: TextIOWrapper) -> None:
        """
        write items to file
        """
        writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
        writer.writeheader()
        writer.writerows([r.as_dict() for r in self.items])

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, key: int) -> TR:
        return self.items[key]

    def __str__(self) -> str:
        return str(self.items)

    def __iter__(self) -> Iterator[TR]:
        return iter(self.items)

    def append(self, row: TR) -> None:
        """
        Append a new row to the table
        """
        row.set_parent_table(self)
        with self.get_lock():
            self.items.append(row)
            self.sync()

    def get_lock(self) -> Lock:
        return self.lock


class UserRole(enum.Flag):
    ADMIN = enum.auto()
    MANAGER = enum.auto()
    RESIDENT = enum.auto()
    CHOREDOER = enum.auto()


@dataclass(slots=True)
class User(TableRow):
    """
    A User has a name, slack_id, and roles
    """

    name: str = ""
    slack_id: str = ""
    roles: UserRole = UserRole(0)

    @classmethod
    def from_dict(cls, member_dict: dict[str, str]) -> Self:
        name = member_dict["name"]
        slack_id = member_dict["slack_id"]
        roles_text = member_dict["roles"]
        roles = UserRole(0)
        for r in roles_text.split("|"):
            if r == "" or r.isspace():
                continue
            try:
                roles |= UserRole[r.upper()]
            except KeyError:
                logger.error(f"Invalid role in user file: {r}")
                continue

        return cls(name=name, slack_id=slack_id, roles=roles)

    def as_dict(self) -> dict[str, str]:
        d = {k.name: getattr(self, k.name) for k in fields(self)}
        role_text = "|".join(r.name for r in self.roles if r.name is not None)
        d["roles"] = role_text

        return d


class UserTable(PersistentTable[User]):
    """
    A persistent table of users
    """

    def __init__(self, filename: str | Path, create_new: bool = False):
        super().__init__(filename, User, create_new)
        self._update_from_slack()

    def _update_from_slack(self) -> None:
        client = WebClient(token=config.get_slack_bot_token())
        resp = client.users_list()
        try:
            members: list[dict[str,Any]] = resp.get("members", [])
            if members == {}: 
                raise ValueError
        except ValueError:
            logger.error("Error retrieving slack user list!")

        local_users = tuple(u.slack_id for u in self)
        for m in members:
            # ignore users that are deleted, bots, or already in table
            deleted = m["deleted"]
            bot = m["is_bot"]
            uid = m["id"]
            if deleted or bot or uid in local_users:
                continue
            # add to table
            # Sometimes names don't exist
            real_name = m.get("real_name", m["profile"].get("real_name", m.get("name", "NoName")))
            if real_name in tuple(u.name for u in self):
                logger.warning(f"User {real_name} already exists with different UID!")
                continue
            # Default to resident and choredoer
            self.append(
                User(name=real_name, slack_id=uid, roles=UserRole.RESIDENT | UserRole.CHOREDOER)
            )

    def get_user_by_name(self, name: str) -> Optional[User]:
        for u in self:
            if u.name == name:
                return u
        return None


        # self.append(User())


@dataclass(slots=True)
class KitchenAssignment(TableRow):
    """
    A KitchenAssignment has a name, date, and swap_date
    """
    name: str
    date: int
    swap_date: Optional[datetime.date]

    @classmethod
    def from_dict(cls, member_dict: dict[str, str]) -> Self:
        name = member_dict['name']
        date = int(member_dict['date'])
        swap_text = member_dict['swap_date']
        if swap_text == '':
            swap_date = None
        else:
            try:
                swap_date = datetime.datetime.strptime(member_dict['swap_date'], '%Y/%m/%d')
            except ValueError:
                logger.error(
                    f"Could not parse swap date {swap_text} in kitchen assignment for {name}")
                swap_date = None
        return cls(name=name, date=date, swap_date=swap_date)

    def as_dict(self) -> dict[str, str]:
        d = {k.name: getattr(self, k.name) for k in fields(self)}
        d['date'] = str(self.date)
        if self.swap_date is None:
            d['swap_date'] = ''
        else:
            d['swap_date'] = self.swap_date.strftime('%Y/%m/%d')

        return d


class KitchenAssignmentTable(PersistentTable[KitchenAssignment]):
    """
    A persistent table storing kitchen cleaning dates
    """

    def __init__(self, filename: str | Path, create_new: bool = False):
        super().__init__(filename, KitchenAssignment, create_new)

    def get_assignment_by_date(self, date: int) -> Optional[KitchenAssignment]:
        # target date this month
        today = datetime.date.today()
        target_date = today.replace(day=date)
        for a in self:
            if a.swap_date == target_date:
                return a

        # No swap
        for a in self:
            if a.date == date:
                return a

        # No kitchen cleaner today
        return None


user_table = UserTable(SLACK_USER_FILE)
kitchen_assignment_table = KitchenAssignmentTable(KITCHEN_ASSIGNMENT_FILE)


def test() -> None:
    # Make a user table
    t = UserTable("test.csv", create_new=True)
    t.append(User("Dave", "abc123", UserRole.MANAGER))
    t.append(User("Barb", "545454", UserRole.RESIDENT | UserRole.CHOREDOER))

    # Make a new table with file
    t2 = UserTable("test.csv")
    for r in t2:
        print(r)
    # Modify table
    u = t2[0]
    u.slack_id = "xyz456"
    t2[1].roles |= UserRole.ADMIN

    # Make a third table and read back
    t3 = UserTable("test.csv")
    print()
    for r in t3:
        print(r)


def test2() -> None:

    # Test Kitchen assignent table
    k = KitchenAssignmentTable(KITCHEN_ASSIGNMENT_FILE)
    print(k)
    for kr in k:
        print(kr)


if __name__ == "__main__":
    test2()
