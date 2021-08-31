import json
import os
from typing import Callable


class StructByAction(object):
    def __init__(self, initDict, parent=None, parent_key=None, action: Callable = lambda _: _):
        self.parent = parent
        self.dictionary = initDict
        self.parent_key = parent_key
        self.action = action

    def __setitem__(self, key, value):
        if self.parent is None:
            self.dictionary.__setitem__(key, value)
            self.action(self.dictionary)
        else:
            self.dictionary[key] = value
            self.parent.__setitem__(self.parent_key, self.dictionary)

    def __getitem__(self, key):
        tmp_return = self.dictionary[key]
        if isinstance(tmp_return, dict) or isinstance(tmp_return, list):
            return StructByAction(tmp_return, parent=self, parent_key=key, action=self.action)
        else:
            return tmp_return

    def __iter__(self):
        return self.dictionary.__iter__()

    def get(self, key):
        return self.dictionary[key]

    def __str__(self):
        return self.dictionary.__str__()

    def __repr__(self):
        return f"StructByAction({self.dictionary})"

    def __delitem__(self, item):
        del self.dictionary[item]
        self.action(self.dictionary)

    def __contains__(self, item):
        return self.dictionary.__contains__(item)

    # list methods
    def __len__(self):
        return len(self.dictionary)

    def append(self, value):
        self.dictionary.append(value)
        self.action(self.dictionary)

    def __iadd__(self, keys):
        self.dictionary += keys
        self.action(self.dictionary)
        return self

    def insert(self, index, value):
        self.dictionary.insert(index, value)
        self.action(self.dictionary)
        return self

    def __bool__(self):
        return len(self.dictionary) > 0 if isinstance(self.dictionary, list) else len(self.dictionary.keys()) > 0


def save(file, obj, indent=None):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent)


def load(file, indent=None):
    with open(file, encoding="utf-8") as f:
        return StructByAction(json.load(f), action=lambda d: save(file, d, indent))


def loadAdvanced(file, ident=None, content=None):
    if content is not None and not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            f.write(content)
    return load(file, ident)


def isCastToFloatAvailable(data):
    try:
        float(data)
        return True
    except ValueError:
        return False


def isDeserializable(data):
    try:
        if isCastToFloatAvailable(data) or not (data.startswith("{") or data.startswith("[")):
            return {}, False
        return json.loads(data), True
    except (ValueError, TypeError):
        return {}, False
