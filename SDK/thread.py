import threading

from . import listExtension


class ThreadManager(object):
    thread_poll = listExtension.ListExtension()
    
    @classmethod
    def get_main_thread(cls):
        return cls.threadByName("Main")

    @classmethod
    def threadByName(cls, name):
        return cls.thread_poll.find(lambda item: item.name == name)

    def changeInterval(self, name, newInterval):
        thread = self.threadByName(name)
        thread.interval = newInterval

    @classmethod
    def create_task(cls, name, task, *args, **kwargs):
        thread = cls.threadByName(name)
        thread.create_task(task, *args, **kwargs)

    def __getitem__(self, key):
        return self.threadByName(key)


class Thread(threading.Thread):
    def __init__(self, *args, **kwargs) -> None:
        ThreadManager.thread_poll.append(self)
        self.tasks = []
        super().__init__(*args, **kwargs)

    def create_task(self, task, *args, **kwargs):
        self.tasks.append((task, args, kwargs))

    def check_tasks(self):
        while len(self.tasks) > 0:
            task = self.tasks.pop(0)
            task[0](*task[1], **task[2])


class Every(Thread):
    def __init__(self, callback, interval, *args, onExecCallback=None, **kwargs):
        self.callback = callback
        self.interval = interval
        self.event = threading.Event()
        self.onExecCallback = onExecCallback
        self.args = args
        super().__init__(**kwargs)
        self.start()

    # override
    def run(self):
        self.callback(*self.args)
        while not self.event.wait(self.interval):
            if self.onExecCallback is not None:
                self.onExecCallback()
            self.check_tasks()
            self.callback(*self.args)


def every(interval, *myArgs, callback=None, **myKwargs):
    def func_wrap(func):
        return Every(func, interval, *myArgs, onExecCallback=callback, **myKwargs)

    return func_wrap
