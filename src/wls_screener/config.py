"""Configuration objects for the WLS stock screener."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenerConfig:
    """All model parameters in one place.

    The defaults reproduce the Screen A and Screen B methodology used in the
    accompanying research workflow. All weights are explicit so the model can
    be audited and changed without editing feature-engineering code.
    """

    # The Bloomberg WLS membership is supplied by the input workbook. These
    # three strict gates define the investable subset before sector ranking.
    min_price_usd: float = 1.0
    min_adv20_usd: float = 15_000_000.0
    min_market_cap_usd: float = 500_000_000.0

    # Output and portfolio construction
    top_n: int = 20
    target_a_count: int = 3
    target_b_count: int = 2
    target_weight: float = 0.20

    # Missing percentile treatment
    missing_percentile: float = 0.50

    # Screen A weights
    a_return_3m_weight: float = 0.40
    a_eps_revision_weight: float = 0.25
    a_price_confirmation_weight: float = 0.25
    a_return_5d_weight: float = 0.10

    # Screen A price-confirmation subweights
    price_confirmation_ma20_weight: float = 0.40
    price_confirmation_ma50_weight: float = 0.30
    price_confirmation_volume_weight: float = 0.30

    # Screen B weights
    b_catalyst_weight: float = 0.35
    b_volatility_weight: float = 0.30
    b_return_5d_weight: float = 0.20
    b_volume_weight: float = 0.15

    # Catalyst timing rules, measured in business days
    catalyst_near_max_days: int = 5
    catalyst_medium_max_days: int = 10
    catalyst_far_max_days: int = 15
    catalyst_near_score: float = 1.00
    catalyst_medium_score: float = 0.75
    catalyst_far_score: float = 0.50

    # Moving-average windows
    ma_short_window: int = 20
    ma_long_window: int = 50

    # Recent-activity windows
    recent_window: int = 5
    normal_window: int = 20

    def validate(self) -> None:
        """Raise ``ValueError`` when the model configuration is inconsistent."""

        if self.top_n <= 0:
            raise ValueError("top_n must be positive.")

        for name in ("min_price_usd", "min_adv20_usd", "min_market_cap_usd"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative.")

        if self.target_a_count <= 0 or self.target_b_count <= 0:
            raise ValueError("Both target sleeve counts must be positive.")
        if not 0.0 < self.target_weight <= 1.0:
            raise ValueError("target_weight must lie in (0, 1].")
        if abs((self.target_a_count + self.target_b_count) * self.target_weight - 1) > 1e-9:
            raise ValueError("Target position weights must sum to 100%.")

        if not 0.0 <= self.missing_percentile <= 1.0:
            raise ValueError("missing_percentile must lie in [0, 1].")

        a_total = (
            self.a_return_3m_weight
            + self.a_eps_revision_weight
            + self.a_price_confirmation_weight
            + self.a_return_5d_weight
        )
        if abs(a_total - 1.0) > 1e-9:
            raise ValueError(f"Screen A weights must sum to 1. Current sum: {a_total}")

        confirmation_total = (
            self.price_confirmation_ma20_weight
            + self.price_confirmation_ma50_weight
            + self.price_confirmation_volume_weight
        )
        if abs(confirmation_total - 1.0) > 1e-9:
            raise ValueError(
                "Price-confirmation weights must sum to 1. "
                f"Current sum: {confirmation_total}"
            )

        b_total = (
            self.b_catalyst_weight
            + self.b_volatility_weight
            + self.b_return_5d_weight
            + self.b_volume_weight
        )
        if abs(b_total - 1.0) > 1e-9:
            raise ValueError(f"Screen B weights must sum to 1. Current sum: {b_total}")

        if not (
            0 <= self.catalyst_near_max_days
            < self.catalyst_medium_max_days
            < self.catalyst_far_max_days
        ):
            raise ValueError("Catalyst day boundaries must be strictly increasing.")

        if self.recent_window >= self.normal_window:
            raise ValueError("recent_window must be smaller than normal_window.")

        if self.ma_short_window >= self.ma_long_window:
            raise ValueError("ma_short_window must be smaller than ma_long_window.")
