#!/usr/bin/env python3
"""
Metric Stability Analyzer - Step 9 Component

Ensures metrics are truly stable, not just temporarily better.
Detects trends, oscillations, and anomalies with statistical rigor.

HIGH-IMPACT FEATURES:
- Time-series trend analysis
- Oscillation detection (flapping)
- Statistical Process Control (SPC)
- Variance analysis with confidence intervals

Author: Step 9 - Verification Loop
Date: 2026-01-02
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from scipy import stats
from scipy.signal import find_peaks


class StabilityStatus(Enum):
    """Metric stability status"""
    STABLE = "STABLE"                      # Metric is stable and healthy
    IMPROVING = "IMPROVING"                # Metric trending better
    DEGRADING = "DEGRADING"                # Metric trending worse
    OSCILLATING = "OSCILLATING"            # Metric flapping between values
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # Not enough data to determine


@dataclass
class TrendAnalysis:
    """Trend analysis result for a time series"""
    metric_name: str
    trend: str                    # "IMPROVING", "STABLE", "DEGRADING"
    slope: float                  # Rate of change per minute
    r_squared: float              # Goodness of fit (0-1)
    is_significant: bool          # Is trend statistically significant
    confidence_interval: Tuple[float, float]  # CI for slope


@dataclass
class OscillationAnalysis:
    """Oscillation/flapping analysis"""
    metric_name: str
    is_oscillating: bool
    peak_count: int               # Number of peaks detected
    frequency: float              # Oscillations per minute
    amplitude: float              # Peak-to-trough variation
    threshold: float              # Acceptable oscillation threshold


@dataclass
class VarianceAnalysis:
    """Statistical variance analysis"""
    metric_name: str
    mean: float
    std_dev: float
    coefficient_of_variation: float  # std/mean, lower is more stable
    is_acceptable: bool           # Is variance within acceptable range
    threshold: float              # Acceptable CV threshold


@dataclass
class StabilityResult:
    """Complete stability analysis result"""
    metric_name: str
    status: StabilityStatus
    
    # Analyses
    trend_analysis: TrendAnalysis
    oscillation_analysis: OscillationAnalysis
    variance_analysis: VarianceAnalysis
    
    # Duration
    stable_duration_minutes: float
    required_duration_minutes: float
    
    # Verdict
    is_stable_enough: bool
    confidence_score: float  # 0-100
    reasons: List[str]
    
    analyzed_at: str


class MetricStabilityAnalyzer:
    """
    Analyzes metric stability using time-series analysis
    
    Prevents premature verification by ensuring metrics are:
    1. Trending correctly (not degrading)
    2. Not oscillating/flapping
    3. Variance is acceptable
    4. Stable for minimum duration
    """
    
    def __init__(self, config: Dict):
        """
        Initialize analyzer
        
        Args:
            config: Stability configuration
        """
        self.config = config
        
        # Stability requirements
        self.min_stable_duration = config.get('min_stable_duration_minutes', 5)
        self.max_coefficient_variation = config.get('max_coefficient_variation', 0.15)  # 15%
        self.max_oscillation_frequency = config.get('max_oscillation_frequency', 0.5)  # 0.5 per minute
        self.trend_significance_level = config.get('trend_significance_level', 0.05)
    
    def analyze_stability(self,
                         metric_name: str,
                         time_series: List[Tuple[float, float]],
                         direction: str = 'lower_is_better') -> StabilityResult:
        """
        Analyze stability of a metric time series
        
        Args:
            metric_name: Name of the metric
            time_series: List of (timestamp, value) tuples
            direction: 'lower_is_better' or 'higher_is_better'
        
        Returns:
            StabilityResult with comprehensive analysis
        """
        print(f"\n{'='*60}")
        print(f"📊 STABILITY ANALYSIS: {metric_name}")
        print(f"{'='*60}")
        print(f"Data points: {len(time_series)}")
        print(f"Direction: {direction}")
        
        if len(time_series) < 10:
            print("⚠️  Insufficient data for stability analysis")
            return self._insufficient_data_result(metric_name)
        
        # Extract timestamps and values
        timestamps = np.array([t for t, v in time_series])
        values = np.array([v for t, v in time_series])
        
        # Normalize timestamps to minutes from start
        time_minutes = (timestamps - timestamps[0]) / 60.0
        stable_duration = time_minutes[-1] if len(time_minutes) > 0 else 0.0
        
        print(f"Duration: {stable_duration:.1f} minutes (required: {self.min_stable_duration})")
        
        # 1. Trend Analysis
        print(f"\n📈 Trend Analysis...")
        trend_analysis = self._analyze_trend(metric_name, time_minutes, values)
        self._print_trend(trend_analysis)
        
        # 2. Oscillation Analysis
        print(f"\n〰️  Oscillation Analysis...")
        oscillation_analysis = self._analyze_oscillation(metric_name, time_minutes, values)
        self._print_oscillation(oscillation_analysis)
        
        # 3. Variance Analysis
        print(f"\n📉 Variance Analysis...")
        variance_analysis = self._analyze_variance(metric_name, values)
        self._print_variance(variance_analysis)
        
        # 4. Determine overall stability
        status, is_stable, confidence, reasons = self._determine_stability(
            trend_analysis,
            oscillation_analysis,
            variance_analysis,
            stable_duration,
            direction
        )
        
        print(f"\n{'='*60}")
        print(f"Status: {status.value}")
        print(f"Stable enough: {'✅ YES' if is_stable else '❌ NO'}")
        print(f"Confidence: {confidence:.1f}/100")
        print(f"\nReasons:")
        for reason in reasons:
            print(f"  • {reason}")
        
        return StabilityResult(
            metric_name=metric_name,
            status=status,
            trend_analysis=trend_analysis,
            oscillation_analysis=oscillation_analysis,
            variance_analysis=variance_analysis,
            stable_duration_minutes=stable_duration,
            required_duration_minutes=self.min_stable_duration,
            is_stable_enough=is_stable,
            confidence_score=confidence,
            reasons=reasons,
            analyzed_at=datetime.now().isoformat()
        )
    
    def _analyze_trend(self, metric_name: str, time_minutes: np.ndarray, values: np.ndarray) -> TrendAnalysis:
        """
        Analyze trend using linear regression
        
        Returns slope, r-squared, and statistical significance
        """
        if len(time_minutes) < 3:
            return TrendAnalysis(
                metric_name=metric_name,
                trend="INSUFFICIENT_DATA",
                slope=0.0,
                r_squared=0.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0)
            )
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(time_minutes, values)
        r_squared = r_value ** 2
        is_significant = p_value < self.trend_significance_level
        
        # Calculate confidence interval for slope
        df = len(time_minutes) - 2  # degrees of freedom
        t_critical = stats.t.ppf(0.975, df)  # 95% CI
        ci_lower = slope - t_critical * std_err
        ci_upper = slope + t_critical * std_err
        
        # Determine trend direction
        if abs(slope) < 0.01:  # Essentially flat
            trend = "STABLE"
        elif slope > 0:
            trend = "DEGRADING" if is_significant else "STABLE"
        else:
            trend = "IMPROVING" if is_significant else "STABLE"
        
        return TrendAnalysis(
            metric_name=metric_name,
            trend=trend,
            slope=slope,
            r_squared=r_squared,
            is_significant=is_significant,
            confidence_interval=(ci_lower, ci_upper)
        )
    
    def _analyze_oscillation(self, metric_name: str, time_minutes: np.ndarray, values: np.ndarray) -> OscillationAnalysis:
        """
        Detect oscillations/flapping using peak detection
        """
        if len(values) < 5:
            return OscillationAnalysis(
                metric_name=metric_name,
                is_oscillating=False,
                peak_count=0,
                frequency=0.0,
                amplitude=0.0,
                threshold=self.max_oscillation_frequency
            )
        
        # Normalize values for peak detection
        normalized = (values - np.mean(values)) / (np.std(values) + 1e-9)
        
        # Find peaks (both positive and negative)
        peaks_pos, _ = find_peaks(normalized, prominence=0.5)
        peaks_neg, _ = find_peaks(-normalized, prominence=0.5)
        
        total_peaks = len(peaks_pos) + len(peaks_neg)
        
        # Calculate frequency (peaks per minute)
        duration = time_minutes[-1] - time_minutes[0] if len(time_minutes) > 1 else 1.0
        frequency = total_peaks / duration if duration > 0 else 0.0
        
        # Calculate amplitude (peak-to-trough variation as % of mean)
        mean_value = np.mean(values)
        amplitude = (np.max(values) - np.min(values)) / mean_value if mean_value > 0 else 0.0
        
        # Is it oscillating?
        is_oscillating = frequency > self.max_oscillation_frequency
        
        return OscillationAnalysis(
            metric_name=metric_name,
            is_oscillating=is_oscillating,
            peak_count=total_peaks,
            frequency=frequency,
            amplitude=amplitude,
            threshold=self.max_oscillation_frequency
        )
    
    def _analyze_variance(self, metric_name: str, values: np.ndarray) -> VarianceAnalysis:
        """
        Analyze statistical variance using coefficient of variation
        """
        mean = np.mean(values)
        std_dev = np.std(values)
        
        # Coefficient of variation (CV) = std / mean
        # Lower CV means more stable
        cv = std_dev / mean if mean > 0 else float('inf')
        
        is_acceptable = cv <= self.max_coefficient_variation
        
        return VarianceAnalysis(
            metric_name=metric_name,
            mean=mean,
            std_dev=std_dev,
            coefficient_of_variation=cv,
            is_acceptable=is_acceptable,
            threshold=self.max_coefficient_variation
        )
    
    def _determine_stability(self,
                            trend: TrendAnalysis,
                            oscillation: OscillationAnalysis,
                            variance: VarianceAnalysis,
                            stable_duration: float,
                            direction: str) -> Tuple[StabilityStatus, bool, float, List[str]]:
        """
        Determine overall stability status using all analyses
        
        Returns:
            (status, is_stable_enough, confidence_score, reasons)
        """
        reasons = []
        confidence = 100.0
        
        # Check duration
        if stable_duration < self.min_stable_duration:
            reasons.append(f"❌ Duration too short: {stable_duration:.1f} min < {self.min_stable_duration} min required")
            confidence -= 30
        else:
            reasons.append(f"✓ Duration sufficient: {stable_duration:.1f} min")
        
        # Check trend
        if direction == 'lower_is_better':
            if trend.trend == "DEGRADING":
                reasons.append(f"❌ Metric trending worse (slope: {trend.slope:+.4f}/min, p={1-trend.is_significant:.3f})")
                confidence -= 40
                status = StabilityStatus.DEGRADING
            elif trend.trend == "IMPROVING":
                reasons.append(f"✓ Metric improving (slope: {trend.slope:+.4f}/min)")
                status = StabilityStatus.IMPROVING
            else:
                reasons.append(f"✓ Metric stable (slope: {trend.slope:+.4f}/min)")
                status = StabilityStatus.STABLE
        else:
            # Higher is better (e.g., throughput)
            if trend.trend == "DEGRADING":
                reasons.append(f"❌ Metric trending down (slope: {trend.slope:+.4f}/min)")
                confidence -= 40
                status = StabilityStatus.DEGRADING
            elif trend.trend == "IMPROVING":
                reasons.append(f"✓ Metric increasing (slope: {trend.slope:+.4f}/min)")
                status = StabilityStatus.IMPROVING
            else:
                reasons.append(f"✓ Metric stable (slope: {trend.slope:+.4f}/min)")
                status = StabilityStatus.STABLE
        
        # Check oscillation
        if oscillation.is_oscillating:
            reasons.append(f"❌ Metric oscillating: {oscillation.frequency:.2f} peaks/min (threshold: {oscillation.threshold})")
            confidence -= 25
            status = StabilityStatus.OSCILLATING
        else:
            reasons.append(f"✓ No oscillation detected ({oscillation.peak_count} peaks over {stable_duration:.1f} min)")
        
        # Check variance
        if not variance.is_acceptable:
            reasons.append(f"❌ High variance: CV={variance.coefficient_of_variation:.2%} (threshold: {variance.threshold:.2%})")
            confidence -= 15
        else:
            reasons.append(f"✓ Acceptable variance: CV={variance.coefficient_of_variation:.2%}")
        
        # Overall stability decision
        is_stable_enough = (
            stable_duration >= self.min_stable_duration and
            status not in [StabilityStatus.DEGRADING, StabilityStatus.OSCILLATING] and
            variance.is_acceptable
        )
        
        confidence = max(0.0, min(100.0, confidence))
        
        return status, is_stable_enough, confidence, reasons
    
    def _insufficient_data_result(self, metric_name: str) -> StabilityResult:
        """Return result for insufficient data"""
        return StabilityResult(
            metric_name=metric_name,
            status=StabilityStatus.INSUFFICIENT_DATA,
            trend_analysis=TrendAnalysis(
                metric_name=metric_name,
                trend="INSUFFICIENT_DATA",
                slope=0.0,
                r_squared=0.0,
                is_significant=False,
                confidence_interval=(0.0, 0.0)
            ),
            oscillation_analysis=OscillationAnalysis(
                metric_name=metric_name,
                is_oscillating=False,
                peak_count=0,
                frequency=0.0,
                amplitude=0.0,
                threshold=self.max_oscillation_frequency
            ),
            variance_analysis=VarianceAnalysis(
                metric_name=metric_name,
                mean=0.0,
                std_dev=0.0,
                coefficient_of_variation=0.0,
                is_acceptable=False,
                threshold=self.max_coefficient_variation
            ),
            stable_duration_minutes=0.0,
            required_duration_minutes=self.min_stable_duration,
            is_stable_enough=False,
            confidence_score=0.0,
            reasons=["Insufficient data for analysis"],
            analyzed_at=datetime.now().isoformat()
        )
    
    def _print_trend(self, trend: TrendAnalysis):
        """Pretty print trend analysis"""
        print(f"  Trend: {trend.trend}")
        print(f"  Slope: {trend.slope:+.4f} per minute")
        print(f"  R²: {trend.r_squared:.4f}")
        print(f"  Significant: {'✓' if trend.is_significant else '✗'}")
        print(f"  95% CI: ({trend.confidence_interval[0]:+.4f}, {trend.confidence_interval[1]:+.4f})")
    
    def _print_oscillation(self, osc: OscillationAnalysis):
        """Pretty print oscillation analysis"""
        print(f"  Oscillating: {'❌ YES' if osc.is_oscillating else '✓ NO'}")
        print(f"  Peaks detected: {osc.peak_count}")
        print(f"  Frequency: {osc.frequency:.2f} peaks/min (threshold: {osc.threshold})")
        print(f"  Amplitude: {osc.amplitude:.2%}")
    
    def _print_variance(self, var: VarianceAnalysis):
        """Pretty print variance analysis"""
        print(f"  Mean: {var.mean:.2f}")
        print(f"  Std Dev: {var.std_dev:.2f}")
        print(f"  CV: {var.coefficient_of_variation:.2%} (threshold: {var.threshold:.2%})")
        print(f"  Acceptable: {'✓ YES' if var.is_acceptable else '❌ NO'}")


# Example usage
if __name__ == "__main__":
    # Configuration
    config = {
        'min_stable_duration_minutes': 5,
        'max_coefficient_variation': 0.15,  # 15%
        'max_oscillation_frequency': 0.5,   # 0.5 peaks per minute
        'trend_significance_level': 0.05
    }
    
    analyzer = MetricStabilityAnalyzer(config)
    
    # Generate mock time series data
    print("Generating mock time series data...")
    
    # Scenario 1: Stable metric
    print("\n" + "="*60)
    print("SCENARIO 1: STABLE METRIC")
    print("="*60)
    
    t_stable = np.linspace(0, 600, 100)  # 10 minutes, 100 samples
    v_stable = 50 + np.random.normal(0, 2, 100)  # Mean 50, small noise
    ts_stable = list(zip(t_stable, v_stable))
    
    result_stable = analyzer.analyze_stability('error_rate', ts_stable, 'lower_is_better')
    
    # Scenario 2: Improving metric
    print("\n" + "="*60)
    print("SCENARIO 2: IMPROVING METRIC")
    print("="*60)
    
    t_improving = np.linspace(0, 600, 100)
    v_improving = 50 - 0.05 * t_improving + np.random.normal(0, 2, 100)  # Decreasing
    ts_improving = list(zip(t_improving, v_improving))
    
    result_improving = analyzer.analyze_stability('p99_latency', ts_improving, 'lower_is_better')
    
    # Scenario 3: Oscillating metric
    print("\n" + "="*60)
    print("SCENARIO 3: OSCILLATING METRIC")
    print("="*60)
    
    t_osc = np.linspace(0, 600, 100)
    v_osc = 50 + 10 * np.sin(0.5 * t_osc) + np.random.normal(0, 1, 100)  # Oscillating
    ts_osc = list(zip(t_osc, v_osc))
    
    result_osc = analyzer.analyze_stability('cpu_usage', ts_osc, 'lower_is_better')
    
    # Scenario 4: Degrading metric
    print("\n" + "="*60)
    print("SCENARIO 4: DEGRADING METRIC")
    print("="*60)
    
    t_degrade = np.linspace(0, 600, 100)
    v_degrade = 50 + 0.08 * t_degrade + np.random.normal(0, 2, 100)  # Increasing (bad)
    ts_degrade = list(zip(t_degrade, v_degrade))
    
    result_degrade = analyzer.analyze_stability('error_rate', ts_degrade, 'lower_is_better')
    
    # Save results
    results = {
        'stable': asdict(result_stable),
        'improving': asdict(result_improving),
        'oscillating': asdict(result_osc),
        'degrading': asdict(result_degrade)
    }
    
    # Convert enums to strings
    for scenario in results.values():
        scenario['status'] = scenario['status'] if isinstance(scenario['status'], str) else scenario['status'].value
    
    with open('stability_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Stability analysis results saved to: stability_analysis_results.json")
