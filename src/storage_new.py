
from dataclasses import dataclass, fields, astuple
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic
from typing_extensions import Self
import sqlite3
import enum

DB_FILE_NAME = "chorebot.db"
DB_FILE = (Path(__file__).parent / ("../data/" + DB_FILE_NAME)).resolve()


@dataclass
class TableRow(ABC):
    """
    Abstract class for table rows. Subclass with members for columns.
    Modifying members will update associated database entry.
    """

    __slots__ = "_parent_table"

    def __post_init__(self) -> None:
        """
        Called by the dataclass __init__
        """
        self._parent_table: Optional["PersistentTable[Self]"] = None

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)

        # if this is a dataclass member update the database
        if name in (f.name for f in fields(self)):
            self.sync()

    def set_parent_table(self, parent_table: Optional["PersistentTable[Self]"]) -> None:
        self._parent_table = parent_table

    # def get_lock(self) -> Lock:
    #     """
    #     Get the Threading.Lock of the parent table.
    #     """
    #     if not hasattr(self, "_parent_table"):
    #         # we are in TableRow initialization which means row is not yet in table
    #         # and no need to lock
    #         return Lock()
    #     if self._parent_table is None:
    #         # parent table hasn't been set, but row is initialized. Error.
    #         raise ValueError("Cannot get lock. This row does not belong to a table.")
    #     # Get lock from table
    #     return self._parent_table.get_lock()

    def sync(self) -> None:
        """
        Tell the parent table to update this row.
        """

        if not hasattr(self, "_parent_table"):
            # No table, no sync
            return
        if self._parent_table is None:
            # Initialized with no table, error
            raise ValueError("Cannot sync. This row does not belong to a table.")
        return self._parent_table.update(self)

    # @abstractmethod
    # def as_dict(self) -> dict[str, str | int]:
    #     raise NotImplementedError
    #
    # @classmethod
    # @abstractmethod
    # def from_dict(cls, member_dict: dict[str, str | int]) -> Self:
    #     raise NotImplementedError


# TR = TypeVar("TR", bound=TableRow)


class PersistentTable[TR: TableRow]:
    """
    Table-like object that interfaces to a database
    """

    def __init__(self, table_name: str, row_type: type[TR], truncate: bool = False):
        self.table_name = table_name
        self.row_type: type[TR] = row_type
        row_fields = fields(self.row_type)
        self.fieldnames = tuple(f.name for f in row_fields)

        fieldtypes = tuple(f.type.__name__ for f in row_fields
                           if hasattr(f.type, '__name__'))

        if len(row_fields) != len(fieldtypes):
            raise TypeError("Table row type does not have __name__??")

        # print(self.fieldnames[0])
        # print(type(self.fieldnames[0]))
        # print(fields(self.row_type)[0].type.__name__)
        # print(name(fields(self.row_type)[0].type))
        # print(type(fields(self.row_type)[0].type))

        # Create table if it does not exist
        column_str = f"{self.fieldnames[0]} {fieldtypes[0]} PRIMARY KEY, " \
            + ", ".join(f"{n} {t}" for n, t in zip(self.fieldnames[1:], fieldtypes[1:]))
        sql = f"CREATE TABLE IF NOT EXISTS {self.table_name}({column_str})"
        # print(sql)
        con = sqlite3.connect(DB_FILE)
        # truncate table if set
        if truncate:
            con.execute(f"DROP TABLE IF EXISTS {self.table_name}")
        con.execute(sql)
        # res = con.execute(("SELECT name FROM sqlite_master",
        #                    "WHERE type='table'",
        #                    "AND name=?"), self.table_name)
        # table_exists = res.fetchone() is not None
        con.close()

    def append(self, row: TR) -> None:
        """
        Append a new row to the table
        """
        if tuple(f.name for f in fields(row)) != self.fieldnames:
            raise ValueError("Invalid row passed to append")

        row.set_parent_table(self)
        sql = (f"INSERT INTO {self.table_name} VALUES"
               "(" + ", ".join('?' * len(self.fieldnames)) + ")")
        # print(sql)
        # print(astuple(row))
        con = sqlite3.connect(DB_FILE)
        con.execute(sql,
                    astuple(row))
        con.commit()
        con.close()

    # TODO: I'd like row to use TR so that sub tables are bound to the sub row types,
        # but mypy doesn't like that
    def update(self, row: TableRow) -> None:
        """
        Replace a row with the one given if the primary key exists
        """
        # validate field names
        if tuple(f.name for f in fields(row)) != self.fieldnames:
            raise ValueError("Invalid row passed to append")
        # check if exists by primary key (first column)
        pk_col = self.fieldnames[0]
        pk_val = astuple(row)[0]
        con = sqlite3.connect(DB_FILE)
        res = con.execute((f"SELECT {pk_col} FROM {self.table_name} WHERE {pk_col} = ?"),
                          (pk_val,))
        if res.fetchone() is None:
            con.close()
            raise ValueError("Attempt to update row that does not exist")

        # Row exists with this primary key. Replace it.
        sql = f"REPLACE INTO {self.table_name} VALUES(" \
            + ", ".join('?' * len(self.fieldnames)) + ")"
        con.execute(sql, astuple(row))
        con.commit()
        con.close()

    def __len__(self) -> int:
        """
        Return the number of rows in the table
        """
        con = sqlite3.connect(DB_FILE)
        res = con.execute(f"SELECT count() FROM {self.table_name}")
        n = res.fetchone()[0]
        assert isinstance(n, int)
        return n

    # TODO: another type variable for key?
    def __getitem__(self, key: Any) -> TR:
        """
        Return row with primary key of key
        """
        con = sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES)
        res = con.execute(f"SELECT * FROM {self.table_name} WHERE {self.fieldnames[0]} = ?", (key,))
        row = self.row_type(*res.fetchone())
        row.set_parent_table(self)
        con.close()
        return row


# TODO: Add role for monthly manager chore
class UserRole(enum.Flag):
    ADMIN = enum.auto()
    MANAGER = enum.auto()
    RESIDENT = enum.auto()
    CHOREDOER = enum.auto()
    MANAGER_CHOREDOER = enum.auto()

    def adapt(self) -> int:
        return self.value

    @classmethod
    def convert(cls, s: bytes) -> Self:
        return cls(int(s))


sqlite3.register_adapter(UserRole, UserRole.adapt)
sqlite3.register_converter("UserRole", UserRole.convert)


@dataclass(slots=True)
class User(TableRow):
    """
    A user has a slack_id, name, and roles
    """

    id: str = ""
    name: str = ""
    roles: UserRole = UserRole(0)

    # @classmethod
    # def from_dict(cls, member_dict: dict[str, str | int]) -> Self:
    #     return cls(id='123', name='test', roles=UserRole(1))
    #     pass
    #
    # def as_dict(self) -> dict[str, str | int]:
    #     d: dict[str, str | int] = {'foo': 'bar', 'baz': 1}
    #     return d


class UserTable(PersistentTable[User]):
    """
    An interface to the user table database
    """

    TABLE_NAME = 'Users'

    def __init__(self, truncate: bool = False):
        super().__init__(self.TABLE_NAME, User, truncate)


def test() -> None:
    # Add some users
    ut = UserTable(truncate=True)
    u1 = User(id='123', name='user1', roles=(UserRole.ADMIN | UserRole.RESIDENT))
    ut.append(u1)
    u2 = User(id='345', name='user2', roles=(UserRole.MANAGER | UserRole.CHOREDOER))
    ut.append(u2)
    u3 = User(id='678', name='user3', roles=(UserRole.RESIDENT))
    ut.append(u3)

    # print the table
    con = sqlite3.connect(DB_FILE)
    res = con.execute(f'SELECT * FROM {ut.table_name}')
    print(res.fetchall())
    con.close()

    # try changing some users
    u2.name = 'user2 new'
    u3.roles |= UserRole.MANAGER

    # print again
    con = sqlite3.connect(DB_FILE)
    res = con.execute(f'SELECT * FROM {ut.table_name}')
    print(res.fetchall())
    con.close()

    # Get user by id
    u345 = ut['345']
    print(u345)
    print(len(ut))

    # change something
    u345.name = "new again"

    # print again
    con = sqlite3.connect(DB_FILE)
    res = con.execute(f'SELECT * FROM {ut.table_name}')
    print(res.fetchall())
    con.close()


if __name__ == '__main__':
    DB_FILE_NAME = "test.db"
    DB_FILE = (Path(__file__).parent / ("../data/" + DB_FILE_NAME)).resolve()
    test()
