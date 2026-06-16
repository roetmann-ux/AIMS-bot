"""Data-driven motive registry.

A *motive* owns its content-category list (in CSV column order), its gate, per-category
soft-gate thresholds, the Expressions-table rows, and appendix definitions. Everything
downstream (contract parsing, scoring, aggregation, report) is keyed off this registry, so a
motive's engine can be swapped or a new motive added without touching other modules.

Category systems follow McClelland / Atkinson / Winter / Smith (1992, *Motivation and
Personality: Handbook of Thematic Content Analysis*), matching the founder's notebooks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# count of a category across a subject's protocol -> evidence-strength label (AIMS sample wording)
EVIDENCE_BANDS: list[tuple[int, str]] = [
    (0, "None"),
    (1, "Some"),         # example in one or two stories
    (3, "Strong"),       # multiple examples across multiple stories
    (5, "Very Strong"),  # multiple examples within and across multiple stories
]


def evidence_label(count: int) -> str:
    label = "None"
    for lo, name in EVIDENCE_BANDS:
        if count >= lo:
            label = name
    return label


@dataclass(frozen=True)
class Category:
    code: str            # CSV code, e.g. "GA+"
    label: str           # display name, e.g. "Anticipation (positive)"
    definition: str      # one-line definition used in Expressions table + appendix
    kind: str            # "gate" | "imagery" | "expression" | "meta"
    polarity: str = "neutral"   # positive | negative | neutral  (drives narrative tone)
    threshold: float = 0.5      # soft-gate threshold used by the live engine
    is_act_enum: bool = False   # the "Act" columns hold Act+/Act-/Act?/null, not 0/1


@dataclass(frozen=True)
class MotiveSpec:
    key: str                 # "achievement" | "affiliation" | "influence"
    display_name: str        # "Achievement"
    report_label: str        # "Achievement motive"
    gate_code: str           # "AI" | "AffIm" | "PowIm"
    categories: tuple[Category, ...]
    provider_votes_col: str
    fixture: str
    one_liner: str           # "the motive to do things better"
    long_definition: str
    subtypes: tuple[tuple[str, str], ...]
    example_jobs: tuple[str, ...]
    summary_bullets: tuple[str, ...]   # "People with this motive may: ..."

    # --- derived helpers -------------------------------------------------
    def grading_codes(self) -> list[str]:
        return [c.code for c in self.categories]

    def subcat_codes(self) -> list[str]:
        return [c.code for c in self.categories if c.kind in ("expression", "meta")]

    def expression_categories(self) -> list[Category]:
        return [c for c in self.categories if c.kind == "expression"]

    def by_code(self, code: str) -> Optional[Category]:
        for c in self.categories:
            if c.code == code:
                return c
        return None

    def threshold_for(self, code: str) -> float:
        c = self.by_code(code)
        return c.threshold if c else 0.5


# --------------------------------------------------------------------------- Achievement
_ACHIEVEMENT = MotiveSpec(
    key="achievement",
    display_name="Achievement",
    report_label="Achievement motive",
    gate_code="AI",
    provider_votes_col="Provider Votes AI",
    fixture="output_Achievement_V12_W1_deepseek9.csv",
    one_liner="the motive to do things better",
    long_definition=(
        "Energized by meeting and beating goals, personally improving the way things are done, "
        "doing and learning new things — doing better."),
    subtypes=(
        ("Efficiency focus", "Analytically reducing uncertainty; improving performance "
                             "methodically and incrementally."),
        ("Innovation focus", "Creating major conceptual improvements; “step-change” "
                             "performance improvement."),
    ),
    example_jobs=("Consulting (esp. execution)", "Engineering", "Entrepreneur", "Finance",
                  "Sales (esp. shorter-cycle)", "Systems improvement"),
    summary_bullets=("Compete with a standard of excellence",
                     "Want to set, meet, and beat goals",
                     "Want unique accomplishments",
                     "Invest in long-term career choices"),
    categories=(
        Category("AI", "Achievement Imagery", "Whether an achievement concern is present at all", "gate"),
        Category("TI", "Task/Doubtful Imagery", "Doubtful task imagery (not scored in this engine)", "meta"),
        Category("UI", "Unrelated Imagery", "No achievement concern present", "imagery"),
        Category("Need", "Need", "Expresses desire and commitment to reach a goal", "expression", "positive"),
        Category("Act", "Action", "Acts to get to the goal", "expression", "positive", is_act_enum=True),
        Category("GA+", "Anticipation (positive)", "Anticipating goal success", "expression", "positive"),
        Category("GA-", "Anticipation (negative)", "Worried about goal failure", "expression", "negative"),
        Category("BP", "Block in person", "Personal obstacles to the goal", "expression", "negative"),
        Category("BW", "Block in world", "External obstacles to the goal", "expression", "negative"),
        Category("Help", "Help", "Enabler of the goal", "expression", "positive"),
        Category("F+", "Feelings (positive)", "Emotion around goal success", "expression", "positive"),
        Category("F-", "Feelings (negative)", "Emotion around goal failure", "expression", "negative"),
        Category("TH", "Theme", "Story dominated by achievement", "meta", threshold=0.7),
    ),
)

# --------------------------------------------------------------------------- Affiliation
_AFFILIATION = MotiveSpec(
    key="affiliation",
    display_name="Affiliation",
    report_label="Affiliation motive",
    gate_code="AffIm",
    provider_votes_col="Provider Votes AffIm",
    fixture="output_Affiliation_V2_W1.csv",
    one_liner="the motive to maintain warm, personal relationships",
    long_definition=(
        "Energized by getting along with people, belonging to a group, personal relationships, "
        "engaging socially — being friendly."),
    subtypes=(
        ("Trusting", "Belonging, trusting others, giving without expectation of return."),
        ("Anxious", "Worry about damaging relationships or hurting feelings; concern for fairness."),
        ("Mistrustful", "Anticipates failures of relationships; assumes inconsistency in intent."),
    ),
    example_jobs=("Human resources", "Account management", "Teaching & mentoring",
                  "Community & nonprofit", "Customer success", "Team-based roles"),
    summary_bullets=("Establish and maintain warm relationships",
                     "Value belonging and group membership",
                     "Protect personal relationships",
                     "Give support without expecting return"),
    categories=(
        Category("AffIm", "Affiliation Imagery", "Whether an affiliative concern is present at all", "gate"),
        Category("N", "Need", "Stated need for a close, friendly relationship", "expression", "positive"),
        Category("Act", "Action", "Acts to establish or maintain the relationship", "expression", "positive", is_act_enum=True),
        Category("SA", "Anticipation (positive)", "Anticipating a positive, close relationship", "expression", "positive", threshold=0.6),
        Category("Bw", "Block in world", "External obstacle to the relationship", "expression", "negative"),
        Category("F+", "Feelings (positive)", "Positive emotion around connection", "expression", "positive"),
        Category("TH", "Theme", "Story dominated by affiliation", "meta"),
    ),
)

# --------------------------------------------------------------------------- Influence (Power)
_INFLUENCE = MotiveSpec(
    key="influence",
    display_name="Influence",
    report_label="Influence motive",
    gate_code="PowIm",
    provider_votes_col="Provider Votes PowIm",
    fixture="output_Power_V11_W1_deepseek9.csv",
    one_liner="the motive to have impact on others",
    long_definition=(
        "Energized by having an impact or influence on individuals, groups, or the world at "
        "large — having impact. (McClelland's Power motive, relabeled for a business audience.)"),
    subtypes=(
        ("Personalized Power", "Having an impact on others to make oneself feel strong."),
        ("Socialized Influence", "Having an impact on others for the good of the whole."),
        ("Empowerment Drive", "Power shared as power multiplied; growing the group's overall power."),
    ),
    example_jobs=("General management", "Executive leadership", "Politics & policy",
                  "Business development", "Public relations", "Negotiation-heavy roles"),
    summary_bullets=("Have impact on individuals, groups, or the world",
                     "Influence the behavior of others",
                     "Care about reputation and position",
                     "Build and direct coalitions"),
    categories=(
        Category("PowIm", "Influence Imagery", "Whether a concern with impact/influence is present", "gate"),
        Category("Pa+", "Prestige (positive)", "Heightened prestige or position of the actor", "expression", "positive"),
        Category("Pa-", "Prestige (negative)", "Lowered prestige or weakness of the actor", "expression", "negative"),
        Category("N", "Need", "Stated need for impact or influence", "expression", "positive", threshold=0.6),
        Category("Act", "Action", "Instrumental activity toward influence", "expression", "positive", threshold=0.6, is_act_enum=True),
        Category("Bw", "Block in world", "External obstacle to influence", "expression", "negative"),
        Category("SA", "Anticipation", "Anticipating the outcome of influence", "expression", "neutral", threshold=0.6),
        Category("Fa", "Conflict / fear", "Fear of or conflict about having impact", "expression", "negative"),
        Category("F+", "Feelings (positive)", "Positive emotion around impact", "expression", "positive"),
        Category("F-", "Feelings (negative)", "Negative emotion around impact", "expression", "negative"),
        Category("Eff", "Effect", "Produces a clear effect or impact on others", "expression", "positive", threshold=0.6),
        Category("HopeFear", "Hope vs. fear of power", "Net hope-of-power vs. fear-of-power signal", "meta"),
    ),
)

REGISTRY: dict[str, MotiveSpec] = {
    m.key: m for m in (_ACHIEVEMENT, _AFFILIATION, _INFLUENCE)
}
# Aliases so callers can pass "power" or report labels interchangeably.
ALIASES = {"power": "influence", "ach": "achievement", "aff": "affiliation", "pow": "influence"}


def get_motive(key: str) -> MotiveSpec:
    k = (key or "").strip().lower()
    k = ALIASES.get(k, k)
    if k not in REGISTRY:
        raise KeyError(f"Unknown motive {key!r}. Known: {list(REGISTRY)}")
    return REGISTRY[k]


def all_motives() -> list[MotiveSpec]:
    return [_ACHIEVEMENT, _AFFILIATION, _INFLUENCE]
