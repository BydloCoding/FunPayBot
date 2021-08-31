# command + after func
import difflib
import inspect
from . import database
from .jsonExtension import StructByAction


class AfterFunc(database.Struct):
    def __init__(self, **kwargs):
        self.save_by = database.ProtectedProperty("user_id")
        self.user_id = database.Sqlite3Property("", "not null unique")
        self.after_name = ""
        self.args = []
        super().__init__(**kwargs)


command_poll = []  # MutableList<Command>
after_func_poll = {}  # name to callable map


# data class for commands
class Command(object):
    def __init__(self, name, aliases, fixTypo, callableItem):
        self.name = name
        self.aliases = aliases
        self.fixTypo = fixTypo
        self.callable = callableItem


def wait(name, uID, function):
    after_func(name)(function)
    set_after(name, uID)


def command(name, fixTypo=True, aliases=None):
    if aliases is None:
        aliases = []

    def func_wrap(func):
        command_poll.append(Command(name, aliases, fixTypo, func))

    return func_wrap


def after_func_from_lambda(name, func):
    after_func(name)(func)


def after_func(name):
    def func_wrap(func):
        # if name in after_func_poll:
        #    raise Exception(f"After function with name \"{name}\" already exists!")
        after_func_poll[name] = func

    return func_wrap


def set_after(name, uID, args=None):
    if args is None:
        args = []
    struct = AfterFunc(after_name=name, user_id=uID)
    struct.after_name = name
    struct.args = args


def call_command(function, *args):
    function_args = inspect.getfullargspec(function).args
    if len(function_args) == 1:
        return function(args[0])
    function(*args)


def execute_command(botClass):
    selected = database.db.select_one_struct("select * from after_func where user_id = ?",
                                             [botClass.user.id])

    if selected is not None and selected.after_name != "null":
        tmpAfterName = selected.after_name
        selected.after_name = "null"
        doNotReset = False
        if tmpAfterName in after_func_poll:
            doNotReset = after_func_poll[tmpAfterName](botClass) if (isinstance(selected.args,
                                                                                StructByAction) and not selected.args.dictionary) or not selected.args else \
                after_func_poll[tmpAfterName](botClass, selected.args)
        if doNotReset is None or after_func_poll[tmpAfterName].__name__ == "<lambda>":
            doNotReset = False
        if doNotReset:
            selected.after_name = tmpAfterName
        return
    tmpCmd = []
    # loop over arguments
    for i in botClass.txtSplit:
        tmpCmd.append(i)
        name = " ".join(tmpCmd)
        # prefer names over fixed commands
        for cmd in command_poll:
            if cmd.name == name or name in cmd.aliases:
                call_command(cmd.callable, botClass, botClass.args)
                return
        for cmd in command_poll:
            if not cmd.fixTypo:
                continue
            matches = difflib.get_close_matches(name, cmd.aliases, cutoff=0.7)
            if not matches:
                continue
            call_command(cmd.callable, botClass, botClass.args)
            return
