class TrackerAgent:
    VALID_STATUSES = {"saved", "planning", "drafting", "submitted", "interview", "accepted", "rejected"}

    def parse_update(self, text: str, opportunity_id: str | None = None) -> dict:
        lowered = text.lower()
        status = next((item for item in self.VALID_STATUSES if item in lowered), "planning")
        return {
            "opportunity_id": opportunity_id,
            "status": status,
            "next_task": self._next_task(status),
        }

    @staticmethod
    def _next_task(status: str) -> str | None:
        return {
            "saved": "Create a deadline plan.",
            "planning": "Prepare required documents.",
            "drafting": "Review and finalize draft documents.",
            "submitted": "Monitor email and application portal.",
            "interview": "Prepare interview notes.",
        }.get(status)
