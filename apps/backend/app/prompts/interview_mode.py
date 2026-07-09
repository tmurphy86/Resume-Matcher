"""Prompt templates for the anti-hallucination interview mode / gap Q&A loop."""

GAP_QUESTIONS_PROMPT = """You are a career coach helping a candidate strengthen their resume.

Job requirements that need supporting evidence:
{jd_gaps}

Verified facts about the candidate:
{facts_section}

Uncovered resume content (bullets with no fact citations):
{uncovered_bullets}

Generate targeted interview-style questions that would elicit verifiable facts to fill these gaps.
Each question should be specific, actionable, and help gather concrete evidence (metrics, outcomes, examples).

Return JSON:
{{"questions": [
  {{"question": "...", "gap_type": "skill|achievement|responsibility", "jd_keyword": "..."}}
]}}"""
