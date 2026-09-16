"""Create Google Tasks from Gemini's classified output.

Run directly to test:  python -m src.tasks_creator
"""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.auth import get_credentials


def create_task(service, task_description, due_date=None, tasklist="@default"):
    """Create a single Google Task. Returns the created task's ID, or None on failure."""
    body = {"title": task_description}

    if due_date:
        # Google Tasks requires RFC 3339 format: YYYY-MM-DDTHH:MM:SS.000Z
        body["due"] = f"{due_date}T00:00:00.000Z"

    try:
        result = service.tasks().insert(tasklist=tasklist, body=body).execute()
        return result.get("id")
    except HttpError as e:
        print(f"[tasks] ERROR creating task '{task_description}': {e}")
        return None


def create_tasks_from_emails(actionable_emails):
    """Create a Google Task for each actionable email. Returns (created, failed) counts."""
    service = build("tasks", "v1", credentials=get_credentials())

    created, failed = 0, 0
    for email in actionable_emails:
        task_id = create_task(
            service,
            task_description=email["task_description"],
            due_date=email.get("due_date"),
        )
        if task_id:
            print(f"[tasks] created: {email['task_description']} (id={task_id})")
            created += 1
        else:
            failed += 1

    return created, failed


if __name__ == "__main__":
    # Test with fake data — doesn't touch Gmail or Gemini.
    sample_tasks = [
        {"task_description": "Submit Assignment 4 (graph traversal) on the portal", "due_date": "2025-03-17"},
        {"task_description": "Stop by Prof. Iyer's office to discuss research proposal draft", "due_date": None},
    ]

    created, failed = create_tasks_from_emails(sample_tasks)
    print(f"\n{created} created, {failed} failed")