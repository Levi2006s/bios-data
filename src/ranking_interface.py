"""Stage-0 contracts for scoring and ranking existing immutable records.

This module intentionally contains no sequence generation, mutation, search,
optimization, feature extraction implementation, or model training code.
"""

from dataclasses import dataclass
from typing import Literal, Mapping, Protocol, Sequence

Direction = Literal["higher_is_better", "lower_is_better"]


@dataclass(frozen=True)
class ExistingRecord:
    """References an already existing candidate; string fields are immutable."""

    record_id: str
    group_id: str
    heavy_or_vhh: str
    light: str | None = None
    antigen: str | None = None


@dataclass(frozen=True)
class TaskSpec:
    """Versionable semantics for one numeric scoring task."""

    name: str
    direction: Direction
    transform: str
    comparable_group: str


@dataclass(frozen=True)
class Score:
    record_id: str
    task_name: str
    value: float


@dataclass(frozen=True)
class Rank:
    record_id: str
    group_id: str
    value: int


class RankingScorer(Protocol):
    """Scores and ranks supplied records without changing their strings."""

    def encode(self, records: Sequence[ExistingRecord]) -> object:
        ...

    def score(self, features: object, task: TaskSpec) -> Sequence[Score]:
        ...

    def rank(
        self,
        scores: Sequence[Score],
        group_ids: Mapping[str, str],
    ) -> Sequence[Rank]:
        ...
