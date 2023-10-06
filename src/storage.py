import enum
from dataclasses import dataclass, fields
from typing import Any, Self, Iterable, Iterator, TypeVar, Generic, Optional
from abc import ABC, abstractmethod
from threading import Lock
import os
import csv
import shutil
from io import TextIOWrapper
import logging
logger = logging.getLogger(__name__)


@dataclass
class TableRow(ABC):
    """
    Abstract class for table rows. Subclass with members for columns. 
    Modifying members will write parent table to disk.
    """

    __slots__ = '_parent_table'

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
        if not hasattr(self, '_parent_table'):
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
        if not hasattr(self, '_parent_table'):
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
    def from_dict(cls, member_dict: dict[str,str]) -> Self:
        raise NotImplementedError



TR = TypeVar('TR', bound=TableRow)

class PersistentTable(Generic[TR]):
    """
    Table-like object with write through csv file storage

    inspired by: https://code.activestate.com/recipes/576642/
    """

    def __init__(self, filename: str, row_type: type[TR], create_new: bool = False):
        self.filename: str = filename
        self.items: list[TR] = list()
        self.row_type: type[TR] = row_type
        self.fieldnames = [f.name for f in fields(self.row_type)]

        # lock for thread safety
        self.lock = Lock()

        if not create_new and os.access(filename, os.R_OK):
            with open(filename, 'r', newline='') as csvfile:
                self.load(csvfile)

    def load(self, csvfile: Iterable[str]) -> None:
        try:
            reader = csv.DictReader(csvfile)
            # convert each row to a table row
            for row in reader:
                self.items.append(self.row_type.from_dict(row))
        except Exception as e:
            raise ValueError(f"Data file {self.filename} not formatted correctly or something: {e}")

    def sync(self) -> None:
        """
        Open file and write items
        """
        tempname = self.filename + ".tmp"
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

    def close(self) -> None:
        self.sync()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

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
    name: str = ''
    slack_id: str = ''
    roles: UserRole = UserRole(0)

    @classmethod
    def from_dict(cls, member_dict: dict[str,str]) -> Self:
        name = member_dict['name']
        slack_id = member_dict['slack_id']
        roles_text = member_dict['roles']
        roles = UserRole(0)
        for r in roles_text.split('|'):
            if r == '' or r.isspace():
                continue
            try:
                roles |= UserRole[r.upper()]
            except KeyError:
                logger.error(f'Invalid role in user file: {r}')
                continue

        return cls(name=name, slack_id=slack_id, roles=roles)

    def as_dict(self) -> dict[str,str]:
        d = {k.name:getattr(self, k.name) for k in fields(self)}
        role_text = '|'.join(r.name for r in self.roles if r.name is not None)
        d['roles'] = role_text

        return d


class UserTable(PersistentTable[User]):
    """
    A persistent table of users
    """
    def __init__(self, filename: str, create_new: bool = False):
        super().__init__(filename, User, create_new)
        # self.append(User())


def test() -> None:
    # Make a user table
    t = UserTable('test.csv', create_new=True)
    t.append(User('Dave', 'abc123', UserRole.MANAGER))
    t.append(User('Barb', '545454', UserRole.RESIDENT | UserRole.CHOREDOER))
    
    # Make a new table with file
    t2 = UserTable('test.csv')
    for r in t2:
        print(r)
    # Modify table
    u = t2[0]
    u.slack_id = 'xyz456'
    t2[1].roles |= UserRole.ADMIN

    # Make a third table and read back
    t3 = UserTable('test.csv')
    print()
    for r in t3:
        print(r)


if __name__ == "__main__":
    test()
