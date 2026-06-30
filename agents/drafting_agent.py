from app.config import Settings, get_settings
from tools.groq_tool import GroqClient


class DraftingAgent:
    def __init__(self, settings: Settings | None = None, client: GroqClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or GroqClient(self.settings)

    def draft(
        self,
        profile: dict,
        opportunity: dict,
        document_type: str,
        cv_text: str | None = None,
        regeneration_instruction: str | None = None,
    ) -> dict:
        system = (
            "You are Compass's document writer. Write the requested document as a real, field-appropriate piece, "
            "not a generic template. Match the genre, length, structure, and tone to the document type. "
            "Use only facts grounded in the profile, CV text, uploaded context, and opportunity record. "
            "Never invent projects, scores, awards, work experience, publications, contacts, deadlines, or names. "
            "Do not mention that you are an AI or that you are using a template. "
            "Return the document text directly as plain text, not JSON."
        )
        doc_guidance = self._document_guidance(document_type)
        instruction_text = f"\nRevision instruction:\n{regeneration_instruction}" if regeneration_instruction else ""
        content = self.client.chat(
            model=self.settings.fast_model,
            system=system,
            user=(
                f"Document type: {document_type}\n\n"
                f"Writing guidance:\n{doc_guidance}\n\n"
                f"Profile:\n{profile}\n\n"
                f"CV text:\n{cv_text or ''}\n\n"
                f"Opportunity:\n{opportunity}"
                f"{instruction_text}"
            ),
            temperature=0.5,
        )
        content = str(content or "")
        if not content.strip():
            raise ValueError("Drafting agent returned empty content.")
        grounding_flags = self.grounding_check(profile, opportunity, content, cv_text)
        return {"document_type": document_type, "content": content, "grounding_flags": grounding_flags}

    @staticmethod
    def _document_guidance(document_type: str) -> str:
        doc = (document_type or "").strip().lower()
        if doc in {"sop", "statement_of_purpose", "statement of purpose"}:
            return (
                "Write a Statement of Purpose in the first person. "
                "Open with the academic or research direction that motivates the application, then explain the fit "
                "between the applicant's background, preparation, and the specific program. "
                "Use a coherent narrative with 3 to 5 short paragraphs: motivation, preparation, research interests, "
                "why this opportunity, and a concise closing. "
                "Focus on academic trajectory, technical preparation, research curiosity, and future goals. "
                "Keep it polished, reflective, and specific, like a real SOP submitted to a graduate program."
            )
        if doc in {"cover_letter", "cover letter"}:
            return (
                "Write a cover letter for an internship, job, or program application. "
                "Address the reader naturally without sounding like a form letter. "
                "Start with the role/opportunity and why the applicant is a fit, then add 2 or 3 focused paragraphs "
                "showing relevant skills, experience, and motivation. "
                "Use a professional but warm tone, make direct claims tied to evidence, and end with a clear closing "
                "that asks for consideration. "
                "Keep it concise, like a real cover letter someone would send."
            )
        if doc in {"professor_email", "email", "faculty_email", "professor email"}:
            return (
                "Write a short, respectful email to a professor or potential supervisor. "
                "Use a subject-line style opening in the first line if helpful, then a brief greeting. "
                "State who the student is, why they are contacting the professor, and what specific research fit or "
                "opportunity they are asking about. "
                "Keep it compact, direct, and polite, with 3 to 6 short paragraphs or very short blocks. "
                "Mention only the most relevant background, avoid long narratives, and end with a clear ask and a courteous sign-off. "
                "It should read like a real outreach email, not an essay."
            )
        if doc in {"motivation_letter", "motivation letter"}:
            return (
                "Write a motivation letter that emphasizes purpose, fit, and future direction. "
                "It should feel more reflective than a cover letter and more personal than a SOP. "
                "Lead with what draws the applicant to the opportunity, then connect background, achievements, "
                "and goals to the program or role. "
                "Use a sincere, polished voice with a strong sense of intent, and keep the structure compact and readable."
            )
        if doc in {"recommendation_letter", "recommendation letter"}:
            return (
                "Write as if the recommender is endorsing the applicant from a real relationship. "
                "Use first person from the recommender's point of view. "
                "Open with how the recommender knows the student, then give 2 or 3 concrete examples of performance, "
                "character, initiative, or research ability. "
                "State a clear recommendation in the closing. "
                "It should sound like an actual faculty or supervisor recommendation letter, not a generic praise paragraph."
            )
        if doc in {"cv_review", "resume_review", "resume review", "cv review"}:
            return (
                "Write a review or improvement note for a CV/resume, not a full application letter. "
                "Point out what is strong, what is missing, and what should be rewritten. "
                "Use concise, actionable language and focus on clarity, impact, and relevance to the target opportunity."
            )
        return (
            "Write a document that clearly matches the requested type. "
            "Adapt the voice, length, and structure to the genre instead of using a universal template. "
            "Prefer concrete, grounded details over broad filler statements."
        )

    def grounding_check(self, profile: dict, opportunity: dict, content: str, cv_text: str | None = None) -> list[str]:
        system = (
            "You check whether a generated application document contains unsupported claims. "
            "Return strict JSON: {\"grounding_flags\": [\"...\"]}. Add a flag for each claim not grounded "
            "in the provided profile, CV text, or opportunity record."
        )
        try:
            result = self.client.json_chat(
                model=self.settings.fast_model,
                system=system,
                user=f"Profile:\n{profile}\nCV text:\n{cv_text or ''}\nOpportunity:\n{opportunity}\nDraft:\n{content}",
                temperature=0.0,
            )
        except Exception:
            return []
        flags = result.get("grounding_flags", [])
        if not isinstance(flags, list):
            return []
        return [str(flag) for flag in flags]
