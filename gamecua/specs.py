"""Strict contracts; unset optional fields are omitted when serialized."""

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1


class Identified(Contract):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")


class PauseSpec(Contract):
    method: Literal["process", "native"]
    settle_seconds: float = Field(default=0.0, ge=0, le=2, allow_inf_nan=False)


class GameSpec(Identified):
    title: str
    status: Literal["verified", "configured", "template"] = "configured"
    steam_app_id: int | None = Field(default=None, gt=0)
    window_title: str
    window_title_prefix: bool = False
    input_backend: Literal["auto", "xsend", "xtest"] = "auto"
    resolution: tuple[int, int] = (1280, 720)
    mouse_mode: Literal["cursor", "captured"] = "cursor"
    timing: Literal["turn_based", "realtime"] = "turn_based"
    budget: Literal["attempts", "time"] | None = None
    pause: PauseSpec | None = None
    notes: str = ""
    introduction: str = Field(default="", max_length=2000)
    controls: str = Field(default="", max_length=2000)

    @model_serializer(mode="wrap")
    def omit_undeclared_fields(self, handler):
        data = handler(self)
        for name in ("budget", "pause", "introduction", "controls"):
            if not data.get(name):
                data.pop(name, None)
        return data


class ContextSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    window_tokens: int | None = Field(default=None, ge=4096, le=4194304)
    summary_tokens: int = Field(default=2048, ge=256, le=8192)
    recent_turns: int = Field(default=8, ge=1, le=64)
    recent_images: int = Field(default=3, ge=1, le=16)
    image_tokens: int = Field(default=1536, ge=256, le=32768)


class InputButton(Contract):
    description: str = Field(min_length=1, max_length=400)
    keys: list[str] = Field(default_factory=list, max_length=8)
    click: tuple[float, float] | None = None
    drag: tuple[float, float, float, float] | None = None
    scroll: int | None = Field(default=None, ge=-8, le=8)
    pointer: Literal["left", "right", "move", "drag"] | None = None

    @field_validator("keys")
    @classmethod
    def supported_keys(cls, value):
        from .actions import canonical_key

        return [canonical_key(key) for key in value]

    @model_serializer(mode="wrap")
    def omit_unused_inputs(self, handler):
        data = handler(self)
        for name in ("drag", "scroll", "pointer"):
            if data.get(name) is None:
                data.pop(name, None)
        return data


class InputGroup(Contract):
    instructions: str = Field(default="", max_length=400)
    buttons: dict[str, InputButton] = Field(min_length=2, max_length=256)


class InputProfile(Identified):
    game_id: str
    version: int = Field(gt=0)
    step_seconds: float = Field(ge=0.2, le=3, allow_inf_nan=False)
    instructions: str = Field(min_length=1, max_length=1200)
    groups: dict[str, InputGroup] = Field(min_length=1, max_length=4)


class ModelSpec(Identified):
    provider: Literal["together", "openai_compatible", "typesafe"]
    model: str
    base_url: str
    api_key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    status: Literal["verified", "configured", "template"] = "configured"
    vision: bool = True
    generation: dict[str, Any] = Field(default_factory=lambda: {"max_tokens": 12288})
    context: ContextSpec = Field(default_factory=ContextSpec)

    @field_validator("base_url")
    @classmethod
    def safe_endpoint(cls, value):
        return value.rstrip("/")


class Milestone(Identified):
    description: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    points: int = Field(gt=0, le=100)
    prerequisites: list[str] = Field(default_factory=list)
    duplicate_credit: Literal["once_per_trial"] = "once_per_trial"
    scope: Literal["episode"] = "episode"


class Rubric(Identified):
    game_id: str
    version: int = Field(gt=0)
    calibrated: Literal[False] = False
    assessment: Literal["milestones", "endpoint"] = "milestones"
    milestones: list[Milestone] = Field(min_length=1)

    @model_serializer(mode="wrap")
    def omit_default_assessment(self, handler):
        data = handler(self)
        if self.assessment == "milestones":
            data.pop("assessment", None)
        return data


class TrialSpec(Identified):
    game_id: str
    model_id: str = "deepseek-flash"
    rubric_id: str
    total_seconds: float = Field(gt=0, allow_inf_nan=False)
    episode_limit: int | None = Field(default=None, ge=1, le=5)
    condition: Literal["pure_image_no_rules"] = "pure_image_no_rules"
    downtime_policy: Literal["charged"] = "charged"
    provider_failure_policy: Literal[
        "charged_retry_then_interrupt", "freeze_retry_timeout_credit"
    ] = "charged_retry_then_interrupt"
    episode_context: Literal["fresh", "trial_memory"] = "trial_memory"
    recording_fps: int = Field(default=2, ge=1, le=30)
    action_execution: Literal["live", "frozen_steps"] = "live"
    step_seconds: float | None = Field(default=None, ge=0.2, le=3, allow_inf_nan=False)
    agent: str | None = Field(default=None, pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
    agent_options: dict[str, Any] = Field(default_factory=dict)
    inputs_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    observation_age_limit_seconds: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    stale_pixel_delta: float = Field(default=15.0, ge=0, le=255, allow_inf_nan=False)

    @model_serializer(mode="wrap")
    def omit_undeclared_inputs(self, handler):
        data = handler(self)
        for name in ("inputs_id", "episode_limit"):
            if data.get(name) is None:
                data.pop(name, None)
        for name, default in (("observation_age_limit_seconds", 30.0), ("stale_pixel_delta", 15.0)):
            if data.get(name) == default:
                data.pop(name, None)
        return data


TIMEOUT_CREDIT_SECONDS = 600.0


class ProviderLedger(Contract):
    timeout_count: int = Field(default=0, ge=0)
    timeout_credit_seconds: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    request_failures: int = Field(default=0, ge=0)
    freezes: int = Field(default=0, ge=0)
    frozen_seconds: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    operator_reports: int = Field(default=0, ge=0)
    operator_pause_seconds: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    state: Literal["ready", "frozen", "operator_paused"] = "ready"


class TrialRecord(Contract):
    id: str
    evidence_gaps: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["preparing", "running", "interrupted", "completed", "cancelled"] = "preparing"
    reason: str | None = None
    started_at: float | None = None
    deadline: float | None = None
    last_seen: float = 0
    elapsed_seconds: float = 0
    chargeable_seconds: float = 0
    infrastructure_downtime_seconds: float = 0
    effective_seconds: float = 0
    eligible: bool = True
    protocol_failures: list[dict[str, Any]] = Field(default_factory=list)
    episodes: list[dict[str, Any]] = Field(default_factory=list)
    provider_recovery: ProviderLedger | None = None

    @model_serializer(mode="wrap")
    def omit_unused_recovery(self, handler):
        data = handler(self)
        if data.get("provider_recovery") is None:
            data.pop("provider_recovery", None)
        return data
