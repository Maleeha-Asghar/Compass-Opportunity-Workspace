from datetime import date, timedelta


class DeadlinePlannerAgent:
    DEFAULT_STEPS = (
        ("Confirm eligibility and official deadline", 21),
        ("Draft statement or cover letter", 10),
        ("Final review and submit application", 2),
    )

    def create_plan(self, opportunity: dict, today: date) -> list[dict]:
        deadline_value = opportunity.get("deadline")
        if not deadline_value:
            return []
        deadline = date.fromisoformat(str(deadline_value))
        if deadline < today:
            return []

        tasks = []
        for title, days_before in self.DEFAULT_STEPS:
            tasks.append(self._task(opportunity, title, deadline, today, days_before))
        required_documents = opportunity.get("required_documents") or []
        for document in required_documents:
            tasks.append(self._task(opportunity, f"Prepare {document}", deadline, today, 14))
        missing_requirements = (opportunity.get("eligibility_result") or {}).get("missing_requirements") or []
        for requirement in missing_requirements:
            tasks.append(self._task(opportunity, f"Resolve or confirm {requirement}", deadline, today, 18))
        opportunity_type = str(opportunity.get("opportunity_type") or "").lower()
        document_text = " ".join(str(item).lower() for item in required_documents)
        if "recommendation" in document_text or opportunity_type in {"masters", "scholarship", "fellowship"}:
            tasks.append(self._task(opportunity, "Request recommendation letters", deadline, today, 21))
        if "transcript" not in document_text:
            tasks.append(self._task(opportunity, "Prepare transcript", deadline, today, 14))
        return self._unique_by_title(tasks)

    @staticmethod
    def _task(opportunity: dict, title: str, deadline: date, today: date, days_before: int) -> dict:
        due_date = deadline - timedelta(days=days_before)
        if due_date < today:
            due_date = today
        return {
            "opportunity_id": opportunity.get("id"),
            "title": title,
            "due_date": due_date.isoformat(),
            "status": "pending",
        }

    @staticmethod
    def _unique_by_title(tasks: list[dict]) -> list[dict]:
        seen = set()
        output = []
        for task in tasks:
            if task["title"] in seen:
                continue
            seen.add(task["title"])
            output.append(task)
        return output
