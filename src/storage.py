import config
import enum
from dataclasses import dataclass, fields
import datetime
from slack_sdk import WebClient
from typing import Any, Iterable, Iterator, TypeVar, Generic, Optional
from typing_extensions import Self
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
KITCHEN_ASSIGNMENT_FILE = (Path(__file__).parent 
    / "../data/kitchen_assignments.csv").resolve()
CHORE_COMP_FILE = (Path(__file__).parent / "../data/chore_comp.csv").resolve()


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
        # Get lock while modifying self
        with self.get_lock():
            self.items.clear()
            try:
                reader = csv.DictReader(csvfile)
                # convert each row to a table row
                for row in reader:
                    trow = self.row_type.from_dict(row)
                    trow.set_parent_table(self)
                    self.items.append(trow)
                    # No need to sync while loading
            except Exception as e:
                raise ValueError(
                    f"Data file {self.filename} not formatted correctly or something: {e}"
                )

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


# TODO: Add role for monthly manager chore
class UserRole(enum.Flag):
    ADMIN = enum.auto()
    MANAGER = enum.auto()
    RESIDENT = enum.auto()
    CHOREDOER = enum.auto()


# TODO: remove name and make id the primary key
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
            members: list[dict[str, Any]] = resp.get("members", [])
            if members == []:
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

    # TODO: create hash table at init
    def get_user_by_name(self, name: str) -> User:
        for u in self:
            if u.name == name:
                return u
        raise ValueError

        # self.append(User())

    def get_user_by_slack_id(self, id: str) -> User:
        for u in self:
            if u.slack_id == id:
                return u
        raise ValueError


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
        name = member_dict["name"]
        date = int(member_dict["date"])
        swap_text = member_dict["swap_date"]
        if swap_text == "":
            swap_date = None
        else:
            try:
                swap_dt = datetime.datetime.strptime(member_dict["swap_date"], "%Y/%m/%d")
                swap_date = datetime.date(swap_dt.year, swap_dt.month, swap_dt.day)
            except ValueError:
                logger.error(
                    f"Could not parse swap date {swap_text} in kitchen assignment for {name}"
                )
                swap_date = None
        return cls(name=name, date=date, swap_date=swap_date)

    def as_dict(self) -> dict[str, str]:
        d = {k.name: getattr(self, k.name) for k in fields(self)}
        d["date"] = str(self.date)
        if self.swap_date is None:
            d["swap_date"] = ""
        else:
            d["swap_date"] = self.swap_date.strftime("%Y/%m/%d")

        return d


class KitchenAssignmentTable(PersistentTable[KitchenAssignment]):
    """
    A persistent table storing kitchen cleaning dates
    """

    def __init__(self, filename: str | Path, create_new: bool = False):
        super().__init__(filename, KitchenAssignment, create_new)
        # Ensure sorted
        self.items.sort(key=lambda i: i.date)

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

class ChoreCompletionFlag(enum.Flag):
    COMPLETE_ON_TIME = enum.auto()
    LATE_PENDING = enum.auto()
    COMPLETE_LATE = enum.auto()
    DID_NOT_COMPLETE = enum.auto()
    MANUALLY_CORRECTED = enum.auto()
    OUT_OF_HOUSE = enum.auto()

class ChoreCompletion(TableRow):
    """
    Chore completion by person for a specific week
    """

    # TODO: date
    date: datetime.date
    # Mapping of names to completion flag
    completion: dict[str, ChoreCompletionFlag]

    def __init__(self, date: datetime.date, comp_dict: dict[str, ChoreCompletionFlag]):
        self.date = date
        self.completion = comp_dict

    def __getitem__(self, key: str) -> ChoreCompletionFlag:
        return self.completion[key]

    def __setitem__(self, key: str, value: ChoreCompletionFlag) -> None:
        with self.get_lock():
            self.completion[key] = value
            self.sync()

    def names(self) -> list[str]:
        return list(self.completion.keys())

    @classmethod
    def from_dict(cls, member_dict: dict[str, str]) -> Self:
        """
        Convert from a dict maping names and text representation of flags to
        mapping names to the actual flag type
        """
        new_dict: dict[str, ChoreCompletionFlag] = dict()
        for column, value in member_dict.items():
            # Check for special date column
            if column == "date":
                try:
                    dt = datetime.datetime.strptime(value, "%Y/%m/%d")
                    date = datetime.date(dt.year, dt.month, dt.day)
                except ValueError:
                    logger.error(f"Could not parse date {dt} in chore completion table")
                    date = datetime.date(1990, 1, 1)
                continue

            flag = ChoreCompletionFlag(0)
            # for each flag in the text
            for f in value.split("|"):
                if f == "" or f.isspace():
                    continue
                try:
                    flag |= ChoreCompletionFlag[f.upper()]
                except KeyError:
                    logger.error(f"Invalid flag in completion file: {f}")
                    continue
            # Put name, flag in new dict
            new_dict[column] = flag

        return cls(date, new_dict)

    def as_dict(self) -> dict[str, str]:
        """
        Return dict mapping names to text representation of flags
        """
        d: dict[str, str] = dict()

        d["date"] = self.date.strftime("%Y/%m/%d")

        # Loop through dict and convert to strings
        for name, flag in self.completion.items():
            role_text = "|".join(f.name for f in flag if f.name is not None)
            d[name] = role_text

        return d


class ChoreCompletionTable(PersistentTable[ChoreCompletion]):
    """
    A table to record chore completion
    """

    names: list[str] = list()

    def __init__(self, filename: str | Path, names: list[str], create_new: bool = False):
        super().__init__(filename, ChoreCompletion, create_new)
        
        # populate cur_names with names loaded from csv if any
        try:
            cur_names = self[0].names()
        except (KeyError, IndexError):
            cur_names = []

        self._ensure_names(cur_names, names)

    def _ensure_names(self, cur_names: list[str], all_names: list[str]) -> None:
        """
        Add names to table if they do not exist
        """
        new_names = [n for n in all_names if n not in cur_names]
        self.names = cur_names + new_names
        for n in new_names:
            for row in self:
                # Set in row member dict directly to avoid multiple syncs
                # We are in __init__ no need to lock
                row.completion[n] = ChoreCompletionFlag(0)
        if new_names:
            self.fieldnames = self.names + ["date"]
            self.sync()

        self.names = cur_names + new_names


# TODO: These are run before logging is set up in main
# user_table = UserTable(SLACK_USER_FILE)
# kitchen_assignment_table = KitchenAssignmentTable(KITCHEN_ASSIGNMENT_FILE)

_user_table: UserTable | None = None
_kitchen_assignment_table: KitchenAssignmentTable | None = None
_chore_completion_table: ChoreCompletionTable | None = None

def init_storage() -> None:
    global _user_table
    global _kitchen_assignment_table
    global _chore_completion_table

    _user_table = UserTable(SLACK_USER_FILE)
    names = [u.name for u in _user_table]
    _kitchen_assignment_table = KitchenAssignmentTable(KITCHEN_ASSIGNMENT_FILE)
    _chore_completion_table = ChoreCompletionTable(CHORE_COMP_FILE, names)

def get_user_table() -> UserTable:
    if not _user_table:
        raise ValueError("Storage not initialized!")
    return _user_table

def get_kitchen_assignment_table() -> KitchenAssignmentTable:
    if not _kitchen_assignment_table:
        raise ValueError("Storage not initialized!")
    return _kitchen_assignment_table

def get_chore_completion_table() -> ChoreCompletionTable:
    if not _chore_completion_table:
        raise ValueError("Storage not initialized!")
    return _chore_completion_table
                         
# TODO rewrite tests to call init_storage classes first
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


def test3() -> None:
    names = ["foo", "bar", "baz"]

    chore_completion_table = ChoreCompletionTable(
        CHORE_COMP_FILE, names, create_new=True)

    row1 = ChoreCompletion(datetime.date(1999, 2, 3), 
        {"foo": ChoreCompletionFlag(2), "bar": ChoreCompletionFlag(1)})

    chore_completion_table.append(row1)

    n2 = ["foo", "baz", "boo"]
    cct2 = ChoreCompletionTable(CHORE_COMP_FILE, n2)
    row2 = ChoreCompletion(
        datetime.date(2001, 4, 4),
       {"foo": ChoreCompletionFlag.COMPLETE_LATE 
            | ChoreCompletionFlag.MANUALLY_CORRECTED, 
        "boo": ChoreCompletionFlag.DID_NOT_COMPLETE})
    cct2.append(row2)


    print("created csvs")


if __name__ == "__main__":
    test3()
