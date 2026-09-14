import argparse
import json
from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pydantic import ConfigDict, Field, model_validator

from lina_agent.domain.career_matching import (
    SKILL_TAXONOMY,
    CandidateDocumentProfile,
    DecisionSignals,
    DecisionWeights,
    JobSkillProfile,
    MatchWeights,
    SkillMention,
    extract_candidate_profile,
    extract_decision_signals,
    extract_job_skill_profile,
    score_job_match,
)
from lina_agent.domain.documents import IngestedDocument
from lina_agent.domain.job_catalog import parse_job_catalog
from lina_agent.domain.models import DomainModel, SourceEvidence
from lina_agent.infrastructure.document_loader import LocalDocumentLoader


class CareerMatchingGoldJob(DomainModel):
    catalog_number: int = Field(ge=1)
    required: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    contextual: tuple[str, ...] = ()
    candidate_supported: tuple[str, ...] = ()
    hard_compatibility: float = Field(ge=0, le=1)
    direction_alignment: float = Field(ge=0, le=1)
    decision_notes: tuple[str, ...] = Field(min_length=1)
    review_status: str = Field(min_length=1)


class MatchingAblation(StrEnum):
    SKILL_ONLY = "skill-only"
    HARD_SKILL = "hard+skill"
    HARD_DIRECTION_SKILL = "hard+direction+skill"


class CareerMatchingGoldDataset(DomainModel):
    model_config = ConfigDict(frozen=True)

    dataset_version: str = Field(min_length=1)
    resume: str = Field(min_length=1)
    job_catalog: str = Field(min_length=1)
    gold_ranking: tuple[int, ...] = Field(min_length=1)
    annotation_policy: str = Field(min_length=1)
    jobs: tuple[CareerMatchingGoldJob, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog_numbers(self) -> "CareerMatchingGoldDataset":
        job_numbers = tuple(job.catalog_number for job in self.jobs)
        if len(set(job_numbers)) != len(job_numbers):
            raise ValueError("gold jobs must use unique catalog numbers")
        if len(set(self.gold_ranking)) != len(self.gold_ranking):
            raise ValueError("gold ranking must not contain duplicates")
        if set(job_numbers) != set(self.gold_ranking):
            raise ValueError("gold ranking must contain every gold job exactly once")
        return self


class CareerMatchingEvaluationReport(DomainModel):
    dataset_version: str
    ablation: MatchingAblation
    weights: MatchWeights
    decision_weights: DecisionWeights | None = None
    job_count: int
    skill_true_positives: int
    skill_false_positives: int
    skill_false_negatives: int
    skill_precision: float = Field(ge=0, le=1)
    skill_recall: float = Field(ge=0, le=1)
    skill_exact_match_rate: float = Field(ge=0, le=1)
    match_precision: float = Field(ge=0, le=1)
    match_recall: float = Field(ge=0, le=1)
    match_exact_match_rate: float = Field(ge=0, le=1)
    citation_count: int = Field(ge=0)
    citation_validity_rate: float = Field(ge=0, le=1)
    citation_support_rate: float = Field(ge=0, le=1)
    predicted_ranking: tuple[int, ...]
    gold_ranking: tuple[int, ...]
    top_1_accuracy: float = Field(ge=0, le=1)
    pairwise_accuracy: float = Field(ge=0, le=1)


class CareerMatchingCalibrationReport(DomainModel):
    baseline: CareerMatchingEvaluationReport
    calibrated: CareerMatchingEvaluationReport
    evaluated_weight_sets: int = Field(ge=1)


class CareerMatchingAblationReport(DomainModel):
    skill_only: CareerMatchingEvaluationReport
    hard_skill: CareerMatchingEvaluationReport
    hard_direction_skill: CareerMatchingEvaluationReport


class AutomaticDecisionSignalReport(DomainModel):
    dataset_version: str
    job_count: int = Field(ge=1)
    hard_signal_coverage: float = Field(ge=0, le=1)
    hard_signal_mae: float | None = Field(default=None, ge=0, le=1)
    direction_signal_coverage: float = Field(ge=0, le=1)
    direction_signal_mae: float | None = Field(default=None, ge=0, le=1)
    unknown_hard_constraint_count: int = Field(ge=0)
    predicted_ranking: tuple[int, ...]
    gold_ranking: tuple[int, ...]
    top_1_accuracy: float = Field(ge=0, le=1)
    pairwise_accuracy: float = Field(ge=0, le=1)


def load_gold_dataset(path: Path) -> CareerMatchingGoldDataset:
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return CareerMatchingGoldDataset.model_validate(payload)


def evaluate_career_matching(
    dataset_path: Path,
    weights: MatchWeights | None = None,
    ablation: MatchingAblation = MatchingAblation.SKILL_ONLY,
) -> CareerMatchingEvaluationReport:
    dataset = load_gold_dataset(dataset_path)
    loader = LocalDocumentLoader()
    resume = loader.load((dataset_path.parent / dataset.resume).resolve())
    catalog = loader.load((dataset_path.parent / dataset.job_catalog).resolve())
    candidate = extract_candidate_profile(resume)
    jobs = parse_job_catalog(catalog)
    if {job.catalog_number for job in jobs} != set(dataset.gold_ranking):
        raise ValueError("parsed catalog numbers must match the gold ranking")

    active_weights = weights or MatchWeights()
    profiles = {job.catalog_number: extract_job_skill_profile(job) for job in jobs}
    labels = {job.catalog_number: job for job in dataset.jobs}
    decision_weights = _decision_weights(ablation)
    matches = tuple(
        sorted(
            (
                score_job_match(
                    candidate,
                    job,
                    profiles[job.catalog_number],
                    active_weights,
                    decision_signals=_decision_signals(labels[job.catalog_number], ablation),
                    decision_weights=decision_weights,
                )
                for job in jobs
            ),
            key=lambda match: (-match.score, match.catalog_number),
        )
    )
    expected_skills = _gold_skill_labels(dataset.jobs)
    predicted_skills = _predicted_skill_labels(profiles)
    true_positives = len(expected_skills & predicted_skills)
    false_positives = len(predicted_skills - expected_skills)
    false_negatives = len(expected_skills - predicted_skills)
    exact_jobs = sum(
        _job_skill_labels(profiles[label.catalog_number], label.catalog_number)
        == _gold_job_skill_labels(label)
        for label in dataset.jobs
    )
    expected_matches = {
        (label.catalog_number, skill)
        for label in dataset.jobs
        for skill in label.candidate_supported
    }
    predicted_matches = {
        (match.catalog_number, evidence_match.skill)
        for match in matches
        for evidence_match in (
            *match.matched_required,
            *match.matched_preferred,
            *match.matched_contextual,
        )
    }
    match_true_positives = len(expected_matches & predicted_matches)
    match_exact_jobs = sum(
        {skill for number, skill in predicted_matches if number == label.catalog_number}
        == set(label.candidate_supported)
        for label in dataset.jobs
    )

    citations = tuple(_all_citations(candidate, profiles.values()))
    valid_citations = sum(citation_is_valid(citation, resume, catalog) for citation in citations)
    supported_citations = sum(
        _citation_supports_skill(skill, citation) for skill, citation in citations
    )
    predicted_ranking = tuple(match.catalog_number for match in matches)
    return CareerMatchingEvaluationReport(
        dataset_version=dataset.dataset_version,
        ablation=ablation,
        weights=active_weights,
        decision_weights=decision_weights,
        job_count=len(jobs),
        skill_true_positives=true_positives,
        skill_false_positives=false_positives,
        skill_false_negatives=false_negatives,
        skill_precision=_ratio(true_positives, true_positives + false_positives),
        skill_recall=_ratio(true_positives, true_positives + false_negatives),
        skill_exact_match_rate=_ratio(exact_jobs, len(dataset.jobs)),
        match_precision=_ratio(match_true_positives, len(predicted_matches)),
        match_recall=_ratio(match_true_positives, len(expected_matches)),
        match_exact_match_rate=_ratio(match_exact_jobs, len(dataset.jobs)),
        citation_count=len(citations),
        citation_validity_rate=_ratio(valid_citations, len(citations)),
        citation_support_rate=_ratio(supported_citations, len(citations)),
        predicted_ranking=predicted_ranking,
        gold_ranking=dataset.gold_ranking,
        top_1_accuracy=float(predicted_ranking[0] == dataset.gold_ranking[0]),
        pairwise_accuracy=_pairwise_accuracy(predicted_ranking, dataset.gold_ranking),
    )


def evaluate_ablations(dataset_path: Path) -> CareerMatchingAblationReport:
    return CareerMatchingAblationReport(
        skill_only=evaluate_career_matching(dataset_path, ablation=MatchingAblation.SKILL_ONLY),
        hard_skill=evaluate_career_matching(dataset_path, ablation=MatchingAblation.HARD_SKILL),
        hard_direction_skill=evaluate_career_matching(
            dataset_path,
            ablation=MatchingAblation.HARD_DIRECTION_SKILL,
        ),
    )


def evaluate_automatic_decision_signals(dataset_path: Path) -> AutomaticDecisionSignalReport:
    dataset = load_gold_dataset(dataset_path)
    loader = LocalDocumentLoader()
    resume = loader.load((dataset_path.parent / dataset.resume).resolve())
    catalog = loader.load((dataset_path.parent / dataset.job_catalog).resolve())
    candidate = extract_candidate_profile(resume)
    jobs = parse_job_catalog(catalog)
    labels = {job.catalog_number: job for job in dataset.jobs}
    extractions = {job.catalog_number: extract_decision_signals(resume, job) for job in jobs}
    matches = tuple(
        sorted(
            (
                score_job_match(
                    candidate,
                    job,
                    extract_job_skill_profile(job),
                    decision_signals=extractions[job.catalog_number].signals,
                    decision_weights=DecisionWeights(),
                )
                for job in jobs
            ),
            key=lambda match: (-match.score, match.catalog_number),
        )
    )
    hard_pairs = tuple(
        (extraction.signals.hard_compatibility, labels[number].hard_compatibility)
        for number, extraction in extractions.items()
        if extraction.signals.hard_compatibility is not None
    )
    direction_pairs = tuple(
        (extraction.signals.direction_alignment, labels[number].direction_alignment)
        for number, extraction in extractions.items()
        if extraction.signals.direction_alignment is not None
    )
    predicted_ranking = tuple(match.catalog_number for match in matches)
    return AutomaticDecisionSignalReport(
        dataset_version=dataset.dataset_version,
        job_count=len(jobs),
        hard_signal_coverage=_ratio(len(hard_pairs), len(jobs)),
        hard_signal_mae=_mean_absolute_error(hard_pairs),
        direction_signal_coverage=_ratio(len(direction_pairs), len(jobs)),
        direction_signal_mae=_mean_absolute_error(direction_pairs),
        unknown_hard_constraint_count=sum(
            item.status == "unknown"
            for extraction in extractions.values()
            for item in extraction.hard_constraints
        ),
        predicted_ranking=predicted_ranking,
        gold_ranking=dataset.gold_ranking,
        top_1_accuracy=float(predicted_ranking[0] == dataset.gold_ranking[0]),
        pairwise_accuracy=_pairwise_accuracy(predicted_ranking, dataset.gold_ranking),
    )


def calibrate_match_weights(dataset_path: Path) -> CareerMatchingCalibrationReport:
    baseline_weights = MatchWeights()
    baseline = evaluate_career_matching(dataset_path, baseline_weights)
    candidates = tuple(_weight_grid())
    reports = tuple(evaluate_career_matching(dataset_path, weights) for weights in candidates)
    calibrated = max(
        reports,
        key=lambda report: (
            report.pairwise_accuracy,
            report.top_1_accuracy,
            -_weight_distance(report.weights, baseline_weights),
        ),
    )
    return CareerMatchingCalibrationReport(
        baseline=baseline,
        calibrated=calibrated,
        evaluated_weight_sets=len(candidates),
    )


def _decision_signals(
    job: CareerMatchingGoldJob,
    ablation: MatchingAblation,
) -> DecisionSignals | None:
    if ablation is MatchingAblation.SKILL_ONLY:
        return None
    return DecisionSignals(
        hard_compatibility=job.hard_compatibility,
        direction_alignment=(
            job.direction_alignment if ablation is MatchingAblation.HARD_DIRECTION_SKILL else None
        ),
        explanations=job.decision_notes,
    )


def _decision_weights(ablation: MatchingAblation) -> DecisionWeights | None:
    if ablation is MatchingAblation.SKILL_ONLY:
        return None
    if ablation is MatchingAblation.HARD_SKILL:
        return DecisionWeights(skill=0.7, hard=0.3, direction=0)
    return DecisionWeights(skill=0.3, hard=0.2, direction=0.5)


def _gold_skill_labels(
    jobs: Iterable[CareerMatchingGoldJob],
) -> set[tuple[int, str, str]]:
    return {label for job in jobs for label in _gold_job_skill_labels(job)}


def _gold_job_skill_labels(job: CareerMatchingGoldJob) -> set[tuple[int, str, str]]:
    return {
        (job.catalog_number, category, skill)
        for category, skills in (
            ("required", job.required),
            ("preferred", job.preferred),
            ("contextual", job.contextual),
        )
        for skill in skills
    }


def _predicted_skill_labels(
    profiles: dict[int, JobSkillProfile],
) -> set[tuple[int, str, str]]:
    return {
        label
        for number, profile in profiles.items()
        for label in _job_skill_labels(profile, number)
    }


def _job_skill_labels(profile: JobSkillProfile, number: int) -> set[tuple[int, str, str]]:
    return {
        (number, category, mention.skill)
        for category, mentions in (
            ("required", profile.required),
            ("preferred", profile.preferred),
            ("contextual", profile.contextual),
        )
        for mention in mentions
    }


def _all_citations(
    candidate: CandidateDocumentProfile,
    job_profiles: Iterable[JobSkillProfile],
) -> Iterable[tuple[str, SourceEvidence]]:
    for mention in candidate.skills:
        yield from _mention_citations(mention)
    for profile in job_profiles:
        for mention in (*profile.required, *profile.preferred, *profile.contextual):
            yield from _mention_citations(mention)


def _mention_citations(mention: SkillMention) -> Iterable[tuple[str, SourceEvidence]]:
    return ((mention.skill, evidence) for evidence in mention.evidence)


def citation_is_valid(
    citation: tuple[str, SourceEvidence],
    resume: IngestedDocument,
    catalog: IngestedDocument,
) -> bool:
    evidence = citation[1]
    if evidence.document_id == resume.id:
        document = resume
    elif evidence.document_id == catalog.id:
        document = catalog
    else:
        return False
    return document.text[evidence.start_offset : evidence.end_offset] == evidence.text


def _citation_supports_skill(skill: str, citation: SourceEvidence) -> bool:
    term = next((term for term in SKILL_TAXONOMY if term.name == skill), None)
    return term is not None and any(
        alias.casefold() == citation.text.casefold() for alias in term.aliases
    )


def _pairwise_accuracy(predicted: tuple[int, ...], gold: tuple[int, ...]) -> float:
    predicted_positions = {number: index for index, number in enumerate(predicted)}
    correct = 0
    total = 0
    for left_index, left in enumerate(gold):
        for right in gold[left_index + 1 :]:
            total += 1
            correct += predicted_positions[left] < predicted_positions[right]
    return _ratio(correct, total)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _mean_absolute_error(pairs: Iterable[tuple[float, float]]) -> float | None:
    values = tuple(abs(predicted - expected) for predicted, expected in pairs)
    return sum(values) / len(values) if values else None


def _weight_grid() -> Iterable[MatchWeights]:
    for required_units in range(5, 10):
        for preferred_units in range(0, 11 - required_units):
            contextual_units = 10 - required_units - preferred_units
            yield MatchWeights(
                required=required_units / 10,
                preferred=preferred_units / 10,
                contextual=contextual_units / 10,
            )


def _weight_distance(left: MatchWeights, right: MatchWeights) -> float:
    return (
        abs(left.required - right.required)
        + abs(left.preferred - right.preferred)
        + abs(left.contextual - right.contextual)
    )


def main(arguments: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate and calibrate skill-evidence ranking.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--ablate", action="store_true")
    parser.add_argument("--auto-signals", action="store_true")
    parsed_arguments = parser.parse_args(arguments)
    selected_modes = sum(
        (parsed_arguments.calibrate, parsed_arguments.ablate, parsed_arguments.auto_signals)
    )
    if selected_modes > 1:
        parser.error("--calibrate, --ablate and --auto-signals are mutually exclusive")
    if parsed_arguments.calibrate:
        report = calibrate_match_weights(parsed_arguments.dataset)
    elif parsed_arguments.ablate:
        report = evaluate_ablations(parsed_arguments.dataset)
    elif parsed_arguments.auto_signals:
        report = evaluate_automatic_decision_signals(parsed_arguments.dataset)
    else:
        report = evaluate_career_matching(parsed_arguments.dataset)
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
