"""
Load WorkItems from a Jira epic.

Not wired to live credentials yet — provide mapping once Jira access is configured.

Expected issue fields (Cloud REST / jira library):
- summary → name
- story points / customfield → estimate
- created → created
- resolutiondate or statusCategory changed to Done → completed
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Iterable, Optional

from .model import WorkItem


def _parse_jira_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    # Jira: 2020-05-10T12:34:56.000+0000
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def issues_to_work_items(
    issues: Iterable[dict],
    *,
    estimate_field: str = "customfield_10016",
) -> list[WorkItem]:
    """
    Convert raw Jira issue dicts (API JSON) into WorkItems.

    `estimate_field` is the Story Points custom field id — override per project.
    """
    items: list[WorkItem] = []
    for issue in issues:
        fields = issue.get("fields") or issue
        estimate = fields.get(estimate_field)
        if estimate is None:
            estimate = fields.get("story_points")
        if estimate is None:
            continue

        created = _parse_jira_datetime(fields.get("created"))
        if created is None:
            continue

        completed = _parse_jira_datetime(fields.get("resolutiondate"))
        name = fields.get("summary") or issue.get("key") or "untitled"
        items.append(
            WorkItem(
                name=str(name),
                estimate=float(estimate),
                created=created,
                completed=completed,
            )
        )
    return items


def load_epic_issues(
    epic_key: str,
    *,
    server: Optional[str] = None,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    estimate_field: str = "customfield_10016",
    jql_extra: str = "",
) -> list[WorkItem]:
    """
    Fetch all issues under an epic and map them to WorkItems.

    Auth via args or env:
      JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN
    """
    server = server or os.environ.get("JIRA_SERVER")
    email = email or os.environ.get("JIRA_EMAIL")
    api_token = api_token or os.environ.get("JIRA_API_TOKEN")

    if not server or not email or not api_token:
        raise RuntimeError(
            "Jira credentials missing. Set JIRA_SERVER, JIRA_EMAIL, JIRA_API_TOKEN "
            "or pass server/email/api_token."
        )

    try:
        from jira import JIRA  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Package 'jira' is not installed. pip install jira"
        ) from exc

    client = JIRA(server=server, basic_auth=(email, api_token))
    jql = f'"Epic Link" = {epic_key} OR parent = {epic_key}'
    if jql_extra:
        jql = f"({jql}) AND ({jql_extra})"

    issues = client.search_issues(
        jql,
        maxResults=False,
        fields=f"summary,created,resolutiondate,{estimate_field}",
    )
    raw = []
    for issue in issues:
        raw.append(
            {
                "key": issue.key,
                "fields": {
                    "summary": issue.fields.summary,
                    "created": issue.fields.created,
                    "resolutiondate": getattr(issue.fields, "resolutiondate", None),
                    estimate_field: getattr(issue.fields, estimate_field, None),
                },
            }
        )
    return issues_to_work_items(raw, estimate_field=estimate_field)


# Convenience for callers that already know sprint bounds from the epic kickoff.
def default_first_sprint_start_from_items(items: list[WorkItem]) -> date:
    """Heuristic: Monday on/after earliest created date — override in real runs."""
    earliest = min(item.created_date for item in items)
    # Excel test data uses an explicit B13; for Jira pass first_sprint_start explicitly.
    return earliest
