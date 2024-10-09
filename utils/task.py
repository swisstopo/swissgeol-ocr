import threading
import typing
import uuid
from dataclasses import dataclass
from typing import Dict, TypeVar

from fastapi import BackgroundTasks

Result = TypeVar("Result")


@dataclass
class Task:
    file: str
    result: Result | None = None


active_tasks: Dict[str, Task] = {}
active_tasks_lock = threading.Lock()


def start(file: str, background_tasks: BackgroundTasks, target: typing.Callable[[], Result]) -> bool:
    with active_tasks_lock:
        if file in active_tasks:
            return False
        active_tasks[file] = Task(file=file)
        background_tasks.add_task(lambda: run(file, target))
        return True


def has_task(file: str) -> bool:
    with active_tasks_lock:
        return file in active_tasks


def collect_result(file: str) -> Result | None:
    with active_tasks_lock:
        task = active_tasks.get(file)
        if task is None or task.result is None:
            return None
        del active_tasks[file]
        return task.result


def run(file: str, target: typing.Callable[[], Result]):
    result = target()
    with active_tasks_lock:
        active_tasks.get(file).result = result