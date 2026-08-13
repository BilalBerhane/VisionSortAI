"""Step 3-4 of the pipeline: the AI vision agent and its structured output.

Two implementations behind the same VisionAgent protocol:
  - AzureVisionAgent: real calls to an Azure OpenAI vision-capable deployment
    (e.g. gpt-4o). Requires AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_KEY /
    AZURE_OPENAI_DEPLOYMENT to be set.
  - MockVisionAgent: deterministic, offline, rule-based stand-in used by
    tests and local dev so the pipeline is fully exercisable without Azure
    credentials.

Output schema (see the workflow diagram, step 4):
    {
      "classification": "duplicate" | "bad" | "document" | "photo",
      "confidence": 0.0-1.0,
      "quality_score": 0.0-1.0,
      "extracted_text": str | null,   # only when classification == "document"
      "category": str | null,          # e.g. "receipt", "invoice", "note", "form"
      "reasoning": str
    }
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Classification = Literal["duplicate", "bad", "document", "photo"]

SYSTEM_PROMPT = """You are a photo triage agent for a personal photo backup system.
For the given photo, decide exactly one classification:
- "bad": the photo is blurry, badly exposed, or otherwise unusable (you will
  also be given pre-computed blur and exposure numbers as supporting evidence)
- "document": the photo is a picture OF a piece of paper (receipt, note,
  form, printed page, etc.) rather than a normal photo
- "photo": none of the above -- a normal, keepable photo

(Duplicate detection happens separately via perceptual hashing, not by you.)

If classification is "document", also extract the visible text (extracted_text)
and assign a short category label (e.g. receipt, invoice, note, form, other).

Respond with ONLY a JSON object matching this schema, no other text:
{"classification": "...", "confidence": 0.0-1.0, "quality_score": 0.0-1.0,
 "extracted_text": "..." or null, "category": "..." or null, "reasoning": "..."}
"""


@dataclass
class AgentResult:
    classification: Classification
    confidence: float
    quality_score: float
    extracted_text: str | None
    category: str | None
    reasoning: str

    @staticmethod
    def from_json(data: dict) -> "AgentResult":
        return AgentResult(
            classification=data["classification"],
            confidence=float(data["confidence"]),
            quality_score=float(data["quality_score"]),
            extracted_text=data.get("extracted_text"),
            category=data.get("category"),
            reasoning=data.get("reasoning", ""),
        )


class VisionAgent(Protocol):
    def classify(self, image_path: Path, local_scores: dict) -> AgentResult: ...


class AzureVisionAgent:
    """Real Azure OpenAI vision agent. Lazily imports/constructs the client
    so importing this module doesn't require Azure credentials to be set."""

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str):
        from openai import AzureOpenAI

        self._deployment = deployment
        self._client = AzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )

    def classify(self, image_path: Path, local_scores: dict) -> AgentResult:
        image_path = Path(image_path)
        b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

        response = self._client.chat.completions.create(
            model=self._deployment,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Pre-computed local scores (for context): {json.dumps(local_scores)}",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        },
                    ],
                },
            ],
        )
        data = json.loads(response.choices[0].message.content)
        return AgentResult.from_json(data)


class MockVisionAgent:
    """Deterministic offline agent for tests / dry runs.

    Rules (based purely on the local_scores passed in, no real vision call):
      - blur_score below `blur_threshold`                -> "bad"
      - exposure flagged bad (is_bad_exposure precomputed) -> "bad"
      - local_scores.get("force_document")                -> "document"
      - otherwise                                          -> "photo"
    confidence defaults to 0.9 but can be overridden via local_scores["force_confidence"]
    for testing the confidence-floor behavior.
    """

    def __init__(self, blur_threshold: float = 100.0):
        self.blur_threshold = blur_threshold

    def classify(self, image_path: Path, local_scores: dict) -> AgentResult:
        confidence = float(local_scores.get("force_confidence", 0.9))

        if local_scores.get("force_document"):
            return AgentResult(
                classification="document",
                confidence=confidence,
                quality_score=0.8,
                extracted_text=local_scores.get("mock_extracted_text", "Sample Ave, $12.34, 2026-08-12"),
                category=local_scores.get("mock_category", "receipt"),
                reasoning="mock: forced document classification",
            )

        blur = local_scores.get("blur_score")
        bad_exposure = local_scores.get("bad_exposure", False)
        if (blur is not None and blur < self.blur_threshold) or bad_exposure:
            return AgentResult(
                classification="bad",
                confidence=confidence,
                quality_score=0.2,
                extracted_text=None,
                category=None,
                reasoning="mock: blur or exposure below threshold",
            )

        return AgentResult(
            classification="photo",
            confidence=confidence,
            quality_score=0.9,
            extracted_text=None,
            category=None,
            reasoning="mock: passed local quality checks",
        )
