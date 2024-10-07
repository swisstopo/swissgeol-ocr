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


type TaskId = str

file_to_task_id: Dict[str, TaskId] = {}
active_tasks: Dict[TaskId, Task] = {}
active_tasks_lock = threading.Lock()


def start(file: str, background_tasks: BackgroundTasks, target: typing.Callable[[TaskId], Result]) -> TaskId | None:
    with active_tasks_lock:
        if file in file_to_task_id:
            return None
        task_id = f"{uuid.uuid4()}"
        file_to_task_id[file] = task_id
        active_tasks[task_id] = Task(file=file)
        background_tasks.add_task(lambda: run(task_id, target))
        return task_id


def has_task(task_id: TaskId) -> bool:
    with active_tasks_lock:
        return task_id in active_tasks


def collect_result(task_id: TaskId) -> Result | None:
    with active_tasks_lock:
        task = active_tasks.get(task_id)
        if task is None or task.result is None:
            return None
        del file_to_task_id[task.file]
        del active_tasks[task_id]
        return task.result


def run(task_id: TaskId, target: typing.Callable[[TaskId], Result]):
    result = target(task_id)
    with active_tasks_lock:
        active_tasks.get(task_id).result = result
