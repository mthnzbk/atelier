"""Atelier örneği: F5 ile çalıştırın, 16. satıra kesme noktası koyun."""
from dataclasses import dataclass


@dataclass
class Task:
    title: str
    completed: bool = False


def progress(tasks: list[Task]) -> float:
    """Tamamlanan görevlerin yüzdesini hesaplar."""
    if not tasks:
        return 0.0
    completed = sum(task.completed for task in tasks)
    return completed / len(tasks) * 100


if __name__ == '__main__':
    tasks = [
        Task('Proje ağacını aç', True),
        Task('Kod tamamlama kullan', True),
        Task('Debugger ile incele'),
    ]
    print(f'Tamamlanan: %{progress(tasks):.0f}')
    for task in tasks:
        marker = '✓' if task.completed else '○'
        print(f'  {marker} {task.title}')
