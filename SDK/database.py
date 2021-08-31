import re
import os
import sqlite3
from sqlite3 import Row
import threading
import typing
from functools import partial

from SDK import (thread, timeExtension, jsonExtension)
from SDK.listExtension import ListExtension


def getter(x: typing.Any, attr: typing.AnyStr): return getattr(x, attr, x)


def adv_getter(x: typing.Any, attr: typing.AnyStr, default: typing.Any): return getattr(x, attr) if hasattr(x,
                                                                                                            attr) \
    else default


def attrgetter(x: typing.Any): return getter(x, "value")


def formAndExpr(baseSql, argsList, getattrFrom, add):
    for i, k in enumerate(add):
        baseSql += f"{k}=?"
        argsList.append(getattr(getattrFrom, k))
        if i != len(add) - 1:
            baseSql += " and "
    return baseSql, argsList


def to_sneak_case(string):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', string).lower()


# Handle all stuff behind Struct instances
class Struct(object):
    table_map = {}
    class_poll = ListExtension([])
    must_implement = []

    @classmethod
    def struct_by_name(cls, table_name, database, **kwargs):
        target_struct: cls = cls.table_map[table_name]
        instance = target_struct(database=database, **kwargs)
        instance.setattr("initialized", True, writeToDatabase=False)
        return instance

    def __init__(self, database=None, **kwargs):
        # creating new struct
        self.db = database or db
        self.table_name = self.get_table_name()
        if kwargs != {}:
            values = ""
            final = []
            for k, v in kwargs.items():
                self.setattr(k, v, False)

            fields = self.getFields()
            keys = ", ".join(lst := list(fields))
            length = len(lst) - 1
            for i, value in enumerate(fields.values()):
                values += "?"
                values += ", " if i != length else ""
                boolean = isinstance(value, list) or isinstance(value, dict)
                final.append(value) if not boolean else final.append(
                    jsonExtension.json.dumps(value))
            fields = self.uniqueField()
            expr = f"select * from {self.table_name} where "
            args = []
            for field in fields:
                if not field in kwargs:
                    raise Exception(
                        f"Property {field} is required by table constructor, but wasn't provided")
            expr, args = formAndExpr(expr, args, self, fields)
            selected = self.db.select_one_struct(
                expr, args, fromSerialized=self)
            if selected is None:
                self.db.execute(
                    f"insert or ignore into {self.table_name} ({keys}) values ({values})", final)
            else:
                self.db.select_one_struct(
                    expr, args, fromSerialized=self)

    def __init_subclass__(cls):
        super().__init_subclass__()
        cls.initialized = False
        instance = cls()
        for x in Struct.must_implement:
            if not ListExtension(vars(instance)).includes(x):
                raise AttributeError(
                    f"Class \"{instance}\" must implement property \"{x}\"")
        Struct.table_map[instance.get_table_name()] = cls
        Struct.class_poll.append(cls)

    def setattr(self, key, value, writeToDatabase=True):
        prev = getattr(self, key, None)
        super().__setattr__(key, value)
        if writeToDatabase and hasattr(self, "db") is not None and hasattr(self, "initialized") and self.initialized:
            if isinstance(prev, jsonExtension.StructByAction):
                super().__setattr__(key, self.boundStructByAction(key, value))
                getattr(self, key).action(None)
            else:
                self.db.write_struct(self, key, value)

    def __setattr__(self, key: typing.Any, value: typing.Any):
        self.setattr(key, value, True)

    @staticmethod
    def toSqlite3Row(k, v):
        declaredValue = attrgetter(v)
        declaredType = Database.convert_type(declaredValue)
        row = f"{k} {declaredType} {adv_getter(v, 'type', '')} default \"{declaredValue}\""

        return row

    def toSqlite3Rows(self):
        row = ""
        realDict = self.getFields()
        dictKeys = list(realDict)
        for i, k in enumerate(dictKeys):
            v = self.__dict__[k]
            row += Struct.toSqlite3Row(k, v)
            row += ", " if i != len(dictKeys) - 1 else ""
        return row

    def uniqueField(self):
        if hasattr(self, "save_by"):
            return convert_to_list_if_needed(attrgetter(self.save_by))
        for k, v in self.getFields().items():
            if isinstance(v, Sqlite3Property) and "unique" in v.type:
                return [k]

    def get_table_name(self):
        if hasattr(self, "table_name"):
            return attrgetter(getattr(self, "table_name"))
        else:
            return to_sneak_case(self.__class__.__name__)

    def getFields(self):
        return {k: v for k, v in vars(self).items() if not isinstance(v, ProtectedProperty) and k not in ["db", "table_name"]}

    def destroy(self):
        fields = self.uniqueField()
        lst = []
        sql = f"delete from {self.table_name} where "
        sql, lst = formAndExpr(sql, lst, self, fields)
        self.db.execute(sql, lst)

    def boundStructByAction(self, key, data):
        data = adv_getter(data, "dictionary", data)
        structByAction = jsonExtension.StructByAction(data)
        structByAction.action = partial(db.save_struct_by_action, self.table_name, key, structByAction, self.uniqueField(),
                                        self)
        return structByAction

    def __repr__(self):
        return f"{self.__class__.__name__}"


def ThreadedStruct(name, one_time=False, **kwargs):
    database = ThreadedDatabase(one_time)
    return Struct.struct_by_name(table_name=name, database=database, **kwargs)


class Sqlite3Property(object):
    def __init__(self, x: typing.Any, y: typing.AnyStr):
        self.value = x
        self.type = y


class ProtectedProperty(object):
    def __init__(self, x: typing.Any):
        self.value = x


def convert_to_list_if_needed(element):
    if not isinstance(element, list):
        return [element]
    else:
        return element


class Database(object):

    typeToTypeCache = {str: "text", dict: "str", list: "str",
                       float: "real", type(None): "null", int: "int", bool: "bool"}

    def __init__(self, file: typing.AnyStr, backup_folder: typing.AnyStr, bot_class, **kwargs):
        self.backup_folder = backup_folder
        folder = os.path.split(file)[0]
        if not os.path.exists(folder):
            os.makedirs(folder)
        self.file = file
        self.bot_class = bot_class
        self.db = sqlite3.connect(file, **kwargs)
        self.row_factory = sqlite3.Row
        self.db.row_factory = self.row_factory
        self.cursor = self.db.cursor()

        for struct in Struct.class_poll:
            struct = struct()
            tableName = struct.get_table_name()
            fields = struct.getFields()
            self.execute(
                f"create table if not exists {tableName} ({struct.toSqlite3Rows()})")
            tableFields = self.get_column_names(tableName)

            for field in fields:
                if field not in tableFields:
                    self.execute(
                        f"alter table {tableName} add column {Struct.toSqlite3Row(field, struct.__dict__[field])}")

        thread.every(self.bot_class.config["db_backup_interval"], name="Backup")(
            self.backup)

    def backup(self):
        if not self.bot_class.config["db_backups"]:
            return

        rawName = self.file.split("/")[-1]
        manager = thread.ThreadManager()
        manager.changeInterval(
            "Backup", self.bot_class.config["db_backup_interval"])
        backup_table = sqlite3.connect(
            f"{self.backup_folder}backup_{timeExtension.now()}_{rawName}")
        self.db.backup(backup_table)

    def select(self, query: typing.AnyStr, args=None):
        if args is None:
            args = []
        self.cursor.execute(query, args)
        return self.cursor.fetchall()

    def create_execute_task(self, query, args=None):
        if args is None:
            args = []
        thread.ThreadManager.get_main_thread().create_task(db.execute, query, args)

    def select_one(self, query: typing.AnyStr, *args):
        if isinstance(args, list):
            self.cursor.execute(query, [str(x) for x in args])
        else:
            self.cursor.execute(query, *args)
        return self.cursor.fetchone()

    def write_struct(self, structToWrite: Struct, changedKey: typing.AnyStr, newValue: typing.Any, execute_function=None):
        execute_function = execute_function or self.execute
        table = structToWrite.table_name
        unique_fields = Struct.table_map[table]().uniqueField()
        sql = f"update or ignore {table} set {changedKey} = ? where "
        argsList = [newValue]
        sql, argsList = formAndExpr(
            sql, argsList, structToWrite, unique_fields)
        execute_function(sql, argsList)

    def select_one_struct(self, query: typing.AnyStr, *args: tuple or jsonExtension.StructByAction,
                          selectedStruct: Row = None,
                          fromSerialized=None, table_name=None, select_function=None, database=None):
        table_name = self.parse_table_name(query, table_name)
        select_function = select_function or self.select_one
        struct = select_function(
            query, *args) if selectedStruct is None else selectedStruct
        if isinstance(args, jsonExtension.StructByAction):
            args = args.dictionary
        if not isinstance(table_name, str):
            raise Exception(
                f"Table name's type is not string (table_name was not provided correctly?)\n{query=}\n{args=}\n{table_name=}")
        myStruct: Struct = Struct.table_map[table_name](database=database or self
                                                        ) if fromSerialized is None else fromSerialized
        if struct is None:
            return None
        for k in struct.keys():
            if k == "db":
                continue
            v = struct[k]
            attr = v
            data, value = jsonExtension.isDeserializable(v)
            if value:
                attr = myStruct.boundStructByAction(k, data)
            if isinstance(getattr(myStruct, k), bool):
                attr = bool(attr)
            myStruct.setattr(k, attr, False)
        myStruct.setattr("initialized", True, writeToDatabase=False)
        return myStruct

    def select_all_structs(self, query: typing.AnyStr, *args, select_function=None):
        select_function = select_function or self.select
        structs = ListExtension.byList(select_function(query, *args))
        return ListExtension.byList([self.select_one_struct(query, *args, selectedStruct=x) for x in structs])

    def save_struct_by_action(self, table_name: typing.AnyStr, key: typing.Any, value: typing.Any,
                              unique_field: typing.Iterable, parent_struct: Struct, _):
        baseSql = f"update {table_name} set {key} = ? where "
        argsList = [jsonExtension.json.dumps(value.dictionary)]
        baseSql, argsList = formAndExpr(
            baseSql, argsList, parent_struct, unique_field)
        self.execute(baseSql, argsList)

    def execute(self, query: typing.AnyStr, args=None):
        if args is None:
            args = []
        for i, k in enumerate(args):
            if type(k) is dict or type(k) is list:
                args[i] = jsonExtension.json.dumps(k)
            elif type(k) is jsonExtension.StructByAction:
                args[i] = jsonExtension.json.dumps(k.dictionary)
        self.cursor.execute(query, args)
        self.db.commit()
        return self.cursor

    def get_column_names(self, table: typing.AnyStr):
        select = self.cursor.execute(f"select * from {table}")
        return [x[0] for x in select.description]

    def parse_table_name(self, query, fromCached=None):
        if fromCached is None:
            return list(tables_in_query(query))[0]
        return fromCached

    def get_table_names(self):
        return [x["name"] for x in self.select("SELECT name FROM sqlite_master WHERE type='table'")]

    @staticmethod
    def convert_type(value):
        return Database.typeToTypeCache[type(value)]

# Databse Class designed to be used with threads, uses same settings as main database


class ThreadedDatabase(object):
    class_poll = {}

    def __new__(cls, one_time=False, **kwargs):
        ident = threading.current_thread().ident
        return super().__new__(cls) if cls.class_poll.get(ident) is None else cls.class_poll[ident]

    def __init__(self, one_time=False, **kwargs) -> None:
        super().__init__(**kwargs)
        if not one_time:
            self.class_poll[thread.ThreadManager.thread_poll.find(
                lambda it: it.ident == threading.current_thread().ident).ident] = self
        self.db = sqlite3.connect(db.file, **kwargs)
        self.cursor = self.db.cursor()
        self.db.row_factory = sqlite3.Row

    def execute(self, query, args=None):
        if args is None:
            args = []
        db.create_execute_task(query, args)

    def select(self, query, args=None):
        if args is None:
            args = []
        return self.db.execute(query, args).fetchall()

    def select_one(self, query, args=None):
        if args is None:
            args = []
        return self.db.execute(query, args).fetchone()

    def select_one_struct(self, *args, **kwargs):
        return db.select_one_struct(*args, select_function=self.select_one, database=self, **kwargs)

    def select_all_structs(self, *args):
        return db.select_all_structs(*args, select_function=self.select)

    def write_struct(self, *args):
        return db.write_struct(*args, execute_function=self.execute)

    def close(self):
        self.db.close()


db: Database = None


# https://grisha.org/blog/2016/11/14/table-names-from-sql/
def tables_in_query(sql_str):
    q = re.sub(r"/\*[^*]*\*+(?:[^*/][^*]*\*+)*/", "", sql_str)
    lines = [line for line in q.splitlines(
    ) if not re.match(r"^\s*(--|#)", line)]
    q = " ".join([re.split(r"--|#", line)[0] for line in lines])
    tokens = re.split(r"[\s)(;]+", q)
    result = set()
    get_next = False
    for tok in tokens:
        if get_next:
            if tok.lower() not in ["", "select"]:
                result.add(tok)
            get_next = False
        get_next = tok.lower() in ["from", "join"]

    return result
