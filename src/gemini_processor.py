"""Classify + extract task info from email bodies using Gemini.

Run directly to test on hardcoded sample emails:
    python -m src.gemini_processor
"""
import json
import os

from google import genai

MODEL = "gemini-3.6-flash"

SYSTEM_PROMPT = """You are a filter that decides whether an email from a \
university context requires the student to take a concrete action.

Rules:
- action_needed = true ONLY for: assignment/submission deadlines, meeting \
requests, explicit requirements the student must complete.
- action_needed = false for: club advertisements, newsletters, general \
announcements, event promotions with no required action, FYI-only content.
- If action_needed is false, task_description and due_date must both be null.
- If a due date is stated or clearly implied, use YYYY-MM-DD. If genuinely \
unclear, use null rather than guessing.

Examples:

Email: "Reminder: Assignment 3 (Dijkstra's algorithm implementation) is due \
this Friday, March 14th by 11:59 PM. Submit via the course portal."
Output: {"action_needed": true, "task_description": "Submit Assignment 3 (Dijkstra's algorithm implementation) via course portal", "due_date": "2025-03-14"}

Email: "Join the Robotics Club this semester! Weekly meetings, free pizza. \
DM us on Instagram @rec_robotics to sign up!"
Output: {"action_needed": false, "task_description": null, "due_date": null}

Email: "Hi, can we meet on Tuesday at 3pm in my office to discuss your \
thesis proposal? - Prof. Sharma"
Output: {"action_needed": true, "task_description": "Meet Prof. Sharma to discuss thesis proposal (Tuesday 3pm, her office)", "due_date": "2025-03-11"}
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "action_needed": {"type": "boolean"},
        "task_description": {"type": ["string", "null"]},
        "due_date": {"type": ["string", "null"], "description": "YYYY-MM-DD or null"},
    },
    "required": ["action_needed", "task_description", "due_date"],
}


def classify_email(client, email):
    """Return a dict: action_needed, task_description, due_date.

    On any failure, returns action_needed=False so the caller safely skips.
    """
    prompt = (
        f"Subject: {email['subject']}\n"
        f"From: {email['sender']}\n"
        f"Body:\n{email['body'][:4000]}"
    )

    try:
        interaction = client.interactions.create(
            model=MODEL,
            input=prompt,
            system_instruction=SYSTEM_PROMPT,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": RESPONSE_SCHEMA,
            },
        )
        result = json.loads(interaction.output_text)
    except Exception as e:
        print(f"[gemini] ERROR for '{email['subject']}': {e}")
        return {"action_needed": False, "task_description": None, "due_date": None}

    return {
        "action_needed": bool(result.get("action_needed")),
        "task_description": result.get("task_description"),
        "due_date": result.get("due_date"),
    }


def classify_emails(emails):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    actionable = []
    for email in emails:
        result = classify_email(client, email)
        tag = "ACTION" if result["action_needed"] else "skip"
        print(f"[gemini] {tag}: {email['subject'][:60]}")
        if result["action_needed"]:
            actionable.append({**email, **result})
    return actionable


if __name__ == "__main__":
    sample_emails = [
        {
            "subject": "Assignment 4 deadline extended",
            "sender": "prof.rao@college.edu",
            "body": "The deadline for Assignment 4 (graph traversal) has been "
                    "moved to next Monday, March 17th, 11:59 PM. Submit on the portal.",
        },
        {
            "subject": "Free food alert! Coding club meetup",
            "sender": "codingclub@college.edu",
            "body": "Come hang out at our weekly meetup this Thursday. Pizza, "
                    "games, and networking. No RSVP needed, just show up!",
        },
        {
            "subject": "Please see me about your proposal",
            "sender": "prof.iyer@college.edu",
            "body": "Can you stop by my office sometime this week to discuss "
                    "your research proposal draft?",
        },
    ]

    results = classify_emails(sample_emails)
    print(f"\n{len(results)} of {len(sample_emails)} flagged as actionable:")
    for r in results:
        print(f"  - {r['task_description']}  (due: {r['due_date']})")


        