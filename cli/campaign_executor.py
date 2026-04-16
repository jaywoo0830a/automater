"""
cli/campaign_executor.py
--------------------------
CampaignExecutor — orchestrates the full CLI pipeline.

    load config → build combos → build specs → assign accounts → execute
"""

from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, TypeVar

from automator.contracts import PostingSpec
from automator.editor import BlogEditor
from automator.ports import TitleChecker
from automator.runner import JobRunner
from automator.title_generator import generate_title, generate_unique_title

from cli.combo_builder import Combo, build_combos
from cli.notifier import build_notifier
from cli.spec_builder import build_spec, merge_account_run

logger = logging.getLogger(__name__)

_T = TypeVar("_T")
_KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanItem:
    """One account's share of the plan."""
    account_username: str
    combo_count:      int


@dataclass(frozen=True)
class ExecutionPlan:
    """Preview of what execute() would do."""
    total_combos:  int
    accounts_used: int
    items:         list[PlanItem]
    sample_titles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ComboRecord:
    """하나의 조합 실행 기록."""
    combo_values: dict[str, str]
    title:        str
    error:        str = ""


@dataclass
class ExecutionResult:
    """Outcome of execute(). Thread-safe via lock."""
    total_attempted:    int = 0
    total_succeeded:    int = 0
    total_failed:       int = 0
    errors:             list[str] = field(default_factory=list)
    succeeded_combos:   list[ComboRecord] = field(default_factory=list)
    failed_combos:      list[ComboRecord] = field(default_factory=list)
    stop_requested:     bool = False  # on_failure=stop 시 True로 설정
    _lock:              threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_success(self, combo: ComboRecord | None = None) -> None:
        with self._lock:
            self.total_attempted += 1
            self.total_succeeded += 1
            if combo:
                self.succeeded_combos.append(combo)

    def record_failure(self, error: str, combo: ComboRecord | None = None) -> None:
        with self._lock:
            self.total_attempted += 1
            self.total_failed += 1
            self.errors.append(error)
            if combo:
                self.failed_combos.append(combo)

    def record_attempt(self) -> None:
        with self._lock:
            self.total_attempted += 1

    def request_stop(self) -> None:
        """on_failure=stop 트리거 — 캠페인 중단 요청."""
        with self._lock:
            self.stop_requested = True


# ---------------------------------------------------------------------------
# Round-robin (pure function)
# ---------------------------------------------------------------------------

def assign_weighted(
    items: list[_T],
    buckets: list[Any],
) -> list[tuple[Any, list[_T]]]:
    """
    Distribute items across buckets by weight, respecting min/max caps.

    Each bucket (account dict) may have:
        "weight"    — distribution ratio (default 1)
        "min_posts" — guaranteed minimum, 0 = none (default 0)
        "max_posts" — hard cap, 0 = unlimited (default 0)

    Algorithm:
        1. Allocate min_posts guarantees first.
        2. Distribute remainder by weight ratio.
        3. Apply max_posts caps — overflow is redistributed.

    Empty buckets excluded from result.
    """
    n = len(items)
    if not buckets or n == 0:
        return []

    def _get(b, key, default):
        return b.get(key, default) if isinstance(b, dict) else default

    weights = [int(_get(b, "weight", 1)) for b in buckets]
    floors = [int(_get(b, "min_posts", 0)) for b in buckets]
    caps = [int(_get(b, "max_posts", 0)) for b in buckets]

    # 1. Allocate min_posts guarantees
    counts = [min(f, n) for f in floors]
    remaining = max(0, n - sum(counts))

    # 2. Distribute remainder by weight
    if remaining > 0:
        extra = _distribute_by_weight(remaining, weights)
        counts = [c + e for c, e in zip(counts, extra)]

    # 3. Apply max_posts caps
    counts = _apply_caps(counts, caps, weights)

    # Slice items by counts
    result: list[tuple[Any, list[_T]]] = []
    offset = 0
    for i, bucket in enumerate(buckets):
        assigned = items[offset:offset + counts[i]]
        offset += counts[i]
        if assigned:
            result.append((bucket, assigned))

    return result


def _distribute_by_weight(n: int, weights: list[int]) -> list[int]:
    """Split n items proportionally by weights."""
    total_weight = sum(weights)
    counts = [n * w // total_weight for w in weights]
    remainder = n - sum(counts)

    fractions = [(n * w / total_weight) - (n * w // total_weight) for w in weights]
    for idx in sorted(range(len(weights)), key=lambda i: fractions[i], reverse=True):
        if remainder <= 0:
            break
        counts[idx] += 1
        remainder -= 1

    return counts


def _apply_caps(
    counts: list[int],
    caps: list[int],
    weights: list[int],
) -> list[int]:
    """
    Enforce max_posts caps. Overflow is redistributed to uncapped buckets
    proportionally by weight. Repeats until stable.
    """
    result = list(counts)

    for _ in range(len(counts)):  # max iterations = number of buckets
        overflow = 0
        uncapped_weight = 0

        for i, cap in enumerate(caps):
            if cap > 0 and result[i] > cap:
                overflow += result[i] - cap
                result[i] = cap
            elif cap == 0 or result[i] < cap:
                uncapped_weight += weights[i]

        if overflow == 0:
            break

        # Redistribute overflow to uncapped buckets by weight
        if uncapped_weight == 0:
            break  # all buckets capped, drop remainder

        distributed = 0
        for i, cap in enumerate(caps):
            if (cap == 0 or result[i] < cap) and uncapped_weight > 0:
                share = overflow * weights[i] // uncapped_weight
                room = (cap - result[i]) if cap > 0 else overflow
                added = min(share, room)
                result[i] += added
                distributed += added

        # Remainder from integer division — give one each to largest uncapped
        leftover = overflow - distributed
        for i in sorted(
            range(len(counts)),
            key=lambda i: weights[i],
            reverse=True,
        ):
            if leftover <= 0:
                break
            if caps[i] == 0 or result[i] < caps[i]:
                result[i] += 1
                leftover -= 1

    return result


# ---------------------------------------------------------------------------
# CampaignExecutor
# ---------------------------------------------------------------------------

EditorFactory = Callable[[dict[str, Any]], BlogEditor]
CheckerFactory = Callable[[dict[str, Any]], TitleChecker]


class CampaignExecutor:
    """
    Orchestrate the full campaign pipeline.

    Dependencies (optional — defaults support dry-run):
        runner:           JobRunner for live execution.
        editor_factory:   account_dict → BlogEditor for live execution.
        checker_factory:  account_dict → TitleChecker for title dedup.

    Philosophy:
        어떤 프로세스든 실패하면 즉시 에러를 던지고 다음 조합으로 넘어간다.
        암묵적·명시적 재시도는 없다.
    """

    def __init__(
        self,
        runner: JobRunner | None = None,
        editor_factory: EditorFactory | None = None,
        checker_factory: CheckerFactory | None = None,
    ) -> None:
        self._runner = runner
        self._editor_factory = editor_factory
        self._checker_factory = checker_factory
        self._seq_next_at: datetime | None = None

    def preview(
        self,
        config: dict[str, Any],
        limit: int | None = None,
    ) -> ExecutionPlan:
        """Build an execution plan without running anything."""
        combos = self._build_combos(config, limit)
        assignments = assign_weighted(combos, config["accounts"])

        sample_titles = []
        for combo in combos[:5]:
            try:
                spec = build_spec(combo, config)
                sample_titles.append(generate_title(spec.title))
            except Exception:
                sample_titles.append("(generation failed)")

        return ExecutionPlan(
            total_combos=len(combos),
            accounts_used=len(assignments),
            items=[
                PlanItem(
                    account_username=acc["username"],
                    combo_count=len(assigned),
                )
                for acc, assigned in assignments
            ],
            sample_titles=sample_titles,
        )

    def execute(
        self,
        config: dict[str, Any],
        dry_run: bool = True,
        limit: int | None = None,
    ) -> ExecutionResult:
        """
        Execute the campaign.

        Args:
            config:  Validated config dict.
            dry_run: If True, build specs but skip runner.run().
            limit:   Max combos to process.
        """
        from cli.progress import ProgressTracker

        combos = self._build_combos(config, limit)
        assignments = assign_weighted(combos, config["accounts"])
        result = ExecutionResult()

        mode_label = "DRY-RUN" if dry_run else "LIVE"
        account_names = [acc["username"] for acc, _ in assignments]
        logger.info("=" * 60)
        logger.info("[campaign] 실행 시작 (%s)", mode_label)
        logger.info("[campaign] 총 조합: %d | 계정: %s", len(combos), ", ".join(account_names))
        logger.info("=" * 60)

        global_run = config.get("run", {})
        on_resume = global_run.get("on_resume", "restart")
        parallel = bool(global_run.get("parallel", False))
        max_workers = int(global_run.get("max_workers", len(assignments)))

        # 즉시 알림을 위해 미리 notifier + 캠페인 이름 준비
        notifier = build_notifier(config.get("notify")) if not dry_run else None
        campaign_name = Path(config.get("_config_path", "campaign")).stem

        # Progress tracking
        config_path = config.get("_config_path", "campaign")
        base_dir = config.get("_base_dir", ".")
        progress = ProgressTracker(config_path, base_dir)

        if on_resume == "restart" and not dry_run:
            progress.reset()
        elif on_resume == "skip" and progress.last_schedule_at:
            # resume 모드: 마지막 예약 시간 복원
            # 단, 복원된 시각이 이미 과거면 현재 시각 기준으로 재계산 (방어)
            try:
                restored = datetime.fromisoformat(progress.last_schedule_at)
                now_kst = datetime.now(tz=_KST)
                if restored < now_kst:
                    logger.warning(
                        "[campaign] 복원된 예약 시간(%s)이 현재(%s)보다 과거입니다 — "
                        "현재 시각 기준으로 남은 조합을 새로 예약합니다",
                        restored.strftime("%Y-%m-%d %H:%M"),
                        now_kst.strftime("%Y-%m-%d %H:%M"),
                    )
                    # progress 파일에서도 제거 (다음 실행 시 혼동 방지)
                    progress.last_schedule_at = ""
                    self._seq_next_at = None
                else:
                    self._seq_next_at = restored
                    logger.info(
                        "[campaign] 예약 시간 복원: %s",
                        self._seq_next_at.strftime("%Y-%m-%d %H:%M"),
                    )
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "[campaign] 예약 시간 복원 실패 (%s) — 현재 시각 기준으로 새로 시작",
                    exc,
                )
                self._seq_next_at = None
        progress.set_total(len(combos))

        if parallel and not dry_run and len(assignments) > 1:
            self._execute_parallel(
                assignments, config, global_run, max_workers, result,
                progress, on_resume, notifier, campaign_name,
            )
        else:
            self._execute_serial(
                assignments, config, global_run, dry_run, result,
                progress, on_resume, notifier, campaign_name,
            )

        logger.info("=" * 60)
        logger.info("[campaign] 실행 완료 (%s)", mode_label)
        logger.info("[campaign] 성공: %d | 실패: %d",
                     result.total_succeeded, result.total_failed)
        if result.errors:
            logger.info("[campaign] 오류 목록:")
            for err in result.errors[:10]:
                logger.info("[campaign]   - %s", err)
        logger.info("=" * 60)

        # 캠페인 요약 알림
        if notifier and not dry_run:
            notifier.send_summary(result, campaign_name)

        return result

    def _execute_serial(
        self,
        assignments: list[tuple[Any, list[Combo]]],
        config: dict[str, Any],
        global_run: dict[str, Any],
        dry_run: bool,
        result: ExecutionResult,
        progress=None,
        on_resume: str = "restart",
        notifier=None,
        campaign_name: str = "",
    ) -> None:
        for account, assigned_combos in assignments:
            # on_failure=stop + 이미 실패 발생 → 다음 계정도 건너뛰기
            if result.stop_requested:
                logger.warning(
                    "[campaign] on_failure=stop 활성 + 실패 감지 — 남은 계정 건너뜀: %s",
                    account.get("username", ""),
                )
                continue
            account_idx = config["accounts"].index(account)
            merged_run = merge_account_run(global_run, account)
            interval = self._parse_interval(merged_run)
            self._execute_batch(
                combos=assigned_combos,
                config=config,
                account_idx=account_idx,
                dry_run=dry_run,
                interval=interval,
                result=result,
                progress=progress,
                on_resume=on_resume,
                notifier=notifier,
                campaign_name=campaign_name,
            )

    def _execute_parallel(
        self,
        assignments: list[tuple[Any, list[Combo]]],
        config: dict[str, Any],
        global_run: dict[str, Any],
        max_workers: int,
        result: ExecutionResult,
        progress=None,
        on_resume: str = "restart",
        notifier=None,
        campaign_name: str = "",
    ) -> None:
        logger.info(
            "[campaign] 병렬 실행: %d 계정, max_workers=%d",
            len(assignments), max_workers,
        )

        def _run_account(account, assigned_combos):
            account_idx = config["accounts"].index(account)
            merged_run = merge_account_run(global_run, account)
            interval = self._parse_interval(merged_run)
            self._execute_batch(
                combos=assigned_combos,
                config=config,
                account_idx=account_idx,
                dry_run=False,
                interval=interval,
                result=result,
                progress=progress,
                on_resume=on_resume,
                notifier=notifier,
                campaign_name=campaign_name,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_account, account, combos): account["username"]
                for account, combos in assignments
            }
            for future in as_completed(futures):
                username = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    logger.error("[campaign] %s 스레드 에러: %s", username, exc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_combos(
        config: dict[str, Any],
        limit: int | None,
    ) -> list[Combo]:
        combos = build_combos(config["keywords"], config["titles"])
        if limit is not None:
            combos = combos[:limit]
        return combos

    def _execute_batch(
        self,
        combos: list[Combo],
        config: dict[str, Any],
        account_idx: int,
        dry_run: bool,
        interval: int,
        result: ExecutionResult,
        progress=None,
        on_resume: str = "restart",
        notifier=None,
        campaign_name: str = "",
    ) -> None:
        account = config["accounts"][account_idx]
        username = account["username"]
        total = len(combos)

        # on_failure 모드 (stop / continue) — merged config 우선, 없으면 global
        merged_run = merge_account_run(config.get("run", {}), account)
        on_failure_mode = str(merged_run.get("on_failure", "continue"))

        logger.info("=" * 50)
        logger.info("[batch] %s — %d개 조합 시작", username, total)
        logger.info("=" * 50)

        # ----------------------------------------------------------
        # Phase 1: Title check — 에디터 열기 전에 모든 제목 확정
        # ----------------------------------------------------------
        tc_config = config.get("title_check", {})
        resolved_titles: dict[int, str] = {}  # combo.index → confirmed title

        if tc_config.get("enabled") and self._checker_factory is not None:
            checker: TitleChecker | None = None
            try:
                checker = self._checker_factory(account)
                logger.info("-" * 50)
                logger.info("[title_check] %s — %d개 조합 검사 시작", username, total)
                logger.info("[title_check] match: %s | delay: %s | max_attempts: %d",
                            tc_config.get("match", "exact"),
                            tc_config.get("delay", "1s ~ 2s"),
                            tc_config.get("max_attempts", 10))
                logger.info("-" * 50)
            except Exception as exc:
                logger.warning(
                    "[title_check] %s — 초기화 실패, 비활성화: %s",
                    username, exc,
                )

            if checker is not None:
                for i, combo in enumerate(combos):
                    combo_index = combo.index - 1
                    if on_resume == "skip" and progress and progress.is_done(combo_index):
                        logger.info("[title_check] [%d/%d] #%d — 이전 완료, 건너뜀", i + 1, total, combo.index)
                        continue
                    try:
                        spec = build_spec(combo, config, account_idx)
                        title = generate_unique_title(
                            spec.title,
                            checker,
                            max_attempts=tc_config.get("max_attempts", 10),
                        )
                        resolved_titles[combo.index] = title
                    except Exception as exc:
                        logger.warning(
                            "[title_check] [%d/%d] #%d 실패: %s — 기본 제목 사용",
                            i + 1, total, combo.index, exc,
                        )

                try:
                    checker.close()
                except Exception:
                    pass

                logger.info("-" * 50)
                logger.info("[title_check] %s — %d/%d 확정", username, len(resolved_titles), total)
                for idx, t in resolved_titles.items():
                    logger.info("[title_check]   #%d → %s", idx, t)
                logger.info("-" * 50)

        # ----------------------------------------------------------
        # Phase 2: Editor — 확정된 제목으로 포스팅
        # ----------------------------------------------------------
        editor = None
        if not dry_run and self._editor_factory is not None:
            try:
                logger.info("[batch] %s — 에디터 초기화 중...", username)
                editor = self._editor_factory(account)
                logger.info("[batch] %s — 에디터 준비 완료", username)
            except Exception as exc:
                logger.error("[batch] %s — 에디터 초기화 실패: %s", username, exc)
                for _ in combos:
                    result.record_failure(str(exc))
                return

        def _close_editor():
            """에디터 및 연결된 브라우저 리소스 정리."""
            if editor is None:
                return
            for attr in ("_context", "_browser"):
                res = getattr(editor, attr, None)
                if res is not None:
                    try:
                        res.close()
                    except Exception:
                        pass

        succeeded_in_batch = 0

        try:
            for i, combo in enumerate(combos):
                # on_failure=stop 이전 실패로 인해 중단 요청된 경우 루프 탈출
                if result.stop_requested:
                    logger.warning(
                        "[batch] %s — on_failure=stop 활성 + 이전 실패 감지, 남은 combo 건너뜀",
                        username,
                    )
                    break

                combo_index = combo.index - 1  # 0-based global index
                progress_label = f"[{i + 1}/{total}]"

                # skip 모드: 이미 완료된 조합 건너뛰기
                if on_resume == "skip" and progress and progress.is_done(combo_index):
                    logger.info("[batch] %s SKIP #%d (이전 실행에서 완료)", progress_label, combo.index)
                    continue

                title = ""
                try:
                    spec = build_spec(combo, config, account_idx)

                    # Phase 1에서 확정된 제목이 있으면 사용, 없으면 기본 생성
                    title = resolved_titles.get(combo.index) or generate_title(spec.title)

                    # Sequential mode: compute schedule_at for each post progressively
                    spec = self._resolve_sequential(spec, i, config, progress)
                    at_label = spec.schedule_at.strftime("%H:%M") if spec.schedule_at else "즉시"

                    logger.info("[batch] %s START %s | %s (예약: %s)", progress_label, username, title, at_label)

                    record = ComboRecord(combo_values=combo.values, title=title)

                    if dry_run:
                        result.record_success(record)
                        logger.info("[batch] %s DRY-RUN %s | %s", progress_label, username, title)
                        succeeded_in_batch += 1
                        continue

                    # 실행 — 실패 시 즉시 예외, 재시도 없음
                    self._run_spec(spec, editor)
                    result.record_success(record)
                    succeeded_in_batch += 1
                    logger.info("[batch] %s DONE %s | %s", progress_label, username, title)
                    if progress:
                        progress.mark_done(combo_index)

                    # Observer result file — one JSON line per successful post
                    _append_observer_result(
                        config,
                        blog_id=account.get("blog_id", username),
                        keyword=_extract_keyword(combo.values, config),
                        title=title,
                        published_at=spec.schedule_at,
                    )

                except Exception as exc:
                    record = ComboRecord(combo_values=combo.values, title=title, error=str(exc))
                    result.record_failure(str(exc), record)
                    logger.error("[batch] %s FAIL %s | %s", progress_label, username, str(exc))

                    # ── 즉시 알림 ──
                    if notifier is not None:
                        try:
                            notifier.send_failure_alert(
                                campaign=campaign_name,
                                username=username,
                                progress=f"{i + 1}/{total}",
                                combo_values=combo.values,
                                title=title,
                                error=str(exc),
                            )
                        except Exception as alert_exc:
                            logger.warning("[batch] 실시간 알림 전송 실패: %s", alert_exc)

                    # ── on_failure=stop 처리 ──
                    if on_failure_mode == "stop":
                        logger.error(
                            "[batch] %s — on_failure=stop: 캠페인 전체 중단 요청",
                            username,
                        )
                        result.request_stop()
                        break

                    continue

                if not dry_run and i < len(combos) - 1 and interval > 0:
                    logger.info("[batch] %s — %d초 대기 중...", username, interval)
                    time.sleep(interval)
        finally:
            _close_editor()

        logger.info("=" * 50)
        logger.info("[batch] %s — 완료 (%d/%d 성공)", username, succeeded_in_batch, total)
        logger.info("=" * 50)

    def _run_spec(self, spec: PostingSpec, editor: BlogEditor) -> None:
        if self._runner is None:
            raise RuntimeError("JobRunner not provided")
        if editor is None:
            raise RuntimeError("editor not initialized")
        self._runner.run(spec, editor)

    def _resolve_sequential(
        self,
        spec: PostingSpec,
        index: int,
        config: dict[str, Any],
        progress=None,
    ) -> PostingSpec:
        """
        For sequential schedule, compute schedule_at progressively.

        Reads interval_lo/interval_hi from config publish.schedule.
        Returns the spec unchanged if schedule is not sequential.
        Saves last_schedule_at to progress for resume support.
        """
        publish_config = config.get("publish", {})
        schedule_raw = publish_config.get("schedule", "")
        if not isinstance(schedule_raw, str) or "++" not in schedule_raw:
            return spec

        from cli.spec_builder import parse_schedule
        parsed = parse_schedule(schedule_raw)
        lo = parsed.get("interval_lo", 0)
        hi = parsed.get("interval_hi", 0) or lo
        interval = random.randint(min(lo, hi), max(lo, hi))

        if self._seq_next_at is None:
            # start_at이 지정되면 그 시각부터, 아니면 now부터
            base = parsed.get("start_at") or datetime.now(tz=_KST)
            self._seq_next_at = base + timedelta(seconds=interval)
        else:
            self._seq_next_at = self._seq_next_at + timedelta(seconds=interval)

        # progress에 마지막 예약 시간 저장 (재시작 시 복원용)
        if progress:
            progress.last_schedule_at = self._seq_next_at.isoformat()

        return replace(spec, schedule_at=self._seq_next_at)

    @staticmethod
    def _parse_interval(run_config: dict[str, Any]) -> int:  # noqa: E301
        raw = run_config.get("interval", "60s")
        if isinstance(raw, (int, float)):
            return int(raw)
        s = str(raw).strip().lower()
        if s.endswith("ms"):
            return 0  # sub-second, treat as 0 for sleep
        if s.endswith("min"):
            return int(s[:-3]) * 60
        if s.endswith("s"):
            return int(s[:-1])
        try:
            return int(s)
        except ValueError:
            return 60


# ---------------------------------------------------------------------------
# Observer result file helpers
# ---------------------------------------------------------------------------

_OBSERVER_RESULTS_FILE = "observer_results.jsonl"


def _extract_keyword(combo_values: dict[str, str], config: dict) -> str:
    """Build the search keyword from combo values.

    Joins all keyword-group values (e.g. region + subject).
    """
    keyword_keys = set(config.get("keywords", {}).keys())
    parts = [v for k, v in combo_values.items() if k in keyword_keys]
    return " ".join(parts) if parts else " ".join(combo_values.values())


def _append_observer_result(
    config: dict,
    *,
    blog_id: str,
    keyword: str,
    title: str,
    published_at: datetime | None,
) -> None:
    """Append one JSON line to the observer results file in the workspace.

    The file lives next to the campaign YAML. The API worker reads it
    after the campaign finishes to INSERT rows into the observer DB.
    """
    import json

    base_dir = config.get("_base_dir", ".")
    out = Path(base_dir) / _OBSERVER_RESULTS_FILE

    entry = {
        "blog_id": blog_id,
        "keyword": keyword,
        "title": title,
        "published_at": published_at.isoformat() if published_at else None,
    }

    try:
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("Failed to write observer result to %s", out)
