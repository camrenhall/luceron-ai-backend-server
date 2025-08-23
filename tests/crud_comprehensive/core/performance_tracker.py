"""
Performance Regression Detection and Trending
Tracks performance metrics over time and detects regressions
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from statistics import mean, median, stdev

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config


@dataclass
class PerformanceMetric:
    """Individual performance measurement"""
    timestamp: str
    test_name: str
    operation: str  # CREATE, READ, UPDATE, DELETE
    duration: float
    resource: str
    success: bool
    environment: str = "local"  # local, ci, staging, production


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison"""
    test_name: str
    operation: str
    resource: str
    avg_duration: float
    p95_duration: float
    p99_duration: float
    sample_count: int
    last_updated: str


@dataclass
class RegressionResult:
    """Result of regression analysis"""
    test_name: str
    operation: str
    resource: str
    current_duration: float
    baseline_avg: float
    baseline_p95: float
    regression_detected: bool
    severity: str  # "none", "minor", "major", "critical"
    change_percent: float
    recommendation: str


class PerformanceTracker:
    """Tracks and analyzes performance metrics over time"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.config = get_config()
        
        if db_path is None:
            # Store in test directory
            test_dir = Path(__file__).parent.parent
            db_path = test_dir / "performance_metrics.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for performance tracking"""
        with sqlite3.connect(self.db_path) as conn:
            # Metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    duration REAL NOT NULL,
                    resource TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    environment TEXT DEFAULT 'local',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Baselines table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_baselines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    avg_duration REAL NOT NULL,
                    p95_duration REAL NOT NULL,
                    p99_duration REAL NOT NULL,
                    sample_count INTEGER NOT NULL,
                    last_updated TEXT NOT NULL,
                    UNIQUE(test_name, operation, resource)
                )
            """)
            
            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_test_op_resource 
                ON performance_metrics(test_name, operation, resource)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON performance_metrics(timestamp)
            """)
            
            conn.commit()
    
    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO performance_metrics 
                (timestamp, test_name, operation, duration, resource, success, environment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.timestamp,
                metric.test_name,
                metric.operation,
                metric.duration,
                metric.resource,
                int(metric.success),
                metric.environment
            ))
            conn.commit()
    
    def record_test_result(self, test_name: str, operation: str, resource: str, 
                          duration: float, success: bool, environment: str = "local"):
        """Convenience method to record a test result"""
        metric = PerformanceMetric(
            timestamp=datetime.now().isoformat(),
            test_name=test_name,
            operation=operation,
            duration=duration,
            resource=resource,
            success=success,
            environment=environment
        )
        self.record_metric(metric)
    
    def get_recent_metrics(self, test_name: str, operation: str, resource: str, 
                          days: int = 30) -> List[PerformanceMetric]:
        """Get recent metrics for a specific test"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, test_name, operation, duration, resource, success, environment
                FROM performance_metrics
                WHERE test_name = ? AND operation = ? AND resource = ?
                  AND timestamp >= ? AND success = 1
                ORDER BY timestamp DESC
            """, (test_name, operation, resource, cutoff_date))
            
            metrics = []
            for row in cursor.fetchall():
                metrics.append(PerformanceMetric(
                    timestamp=row[0],
                    test_name=row[1],
                    operation=row[2],
                    duration=row[3],
                    resource=row[4],
                    success=bool(row[5]),
                    environment=row[6]
                ))
            
            return metrics
    
    def calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile from list of values"""
        if not values:
            return 0.0
        
        values_sorted = sorted(values)
        k = (len(values_sorted) - 1) * percentile / 100
        f = int(k)
        c = k - f
        
        if f == len(values_sorted) - 1:
            return values_sorted[f]
        
        return values_sorted[f] * (1 - c) + values_sorted[f + 1] * c
    
    def update_baseline(self, test_name: str, operation: str, resource: str):
        """Update performance baseline based on recent successful tests"""
        # Get metrics from last 30 days
        metrics = self.get_recent_metrics(test_name, operation, resource, days=30)
        
        if len(metrics) < 5:  # Need at least 5 samples for meaningful baseline
            return
        
        durations = [m.duration for m in metrics]
        
        baseline = PerformanceBaseline(
            test_name=test_name,
            operation=operation,
            resource=resource,
            avg_duration=mean(durations),
            p95_duration=self.calculate_percentile(durations, 95),
            p99_duration=self.calculate_percentile(durations, 99),
            sample_count=len(durations),
            last_updated=datetime.now().isoformat()
        )
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO performance_baselines
                (test_name, operation, resource, avg_duration, p95_duration, p99_duration, sample_count, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                baseline.test_name,
                baseline.operation,
                baseline.resource,
                baseline.avg_duration,
                baseline.p95_duration,
                baseline.p99_duration,
                baseline.sample_count,
                baseline.last_updated
            ))
            conn.commit()
    
    def get_baseline(self, test_name: str, operation: str, resource: str) -> Optional[PerformanceBaseline]:
        """Get performance baseline for a specific test"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT test_name, operation, resource, avg_duration, p95_duration, p99_duration, sample_count, last_updated
                FROM performance_baselines
                WHERE test_name = ? AND operation = ? AND resource = ?
            """, (test_name, operation, resource))
            
            row = cursor.fetchone()
            if row:
                return PerformanceBaseline(*row)
            
            return None
    
    def detect_regression(self, test_name: str, operation: str, resource: str, 
                         current_duration: float) -> RegressionResult:
        """Detect performance regression against baseline"""
        baseline = self.get_baseline(test_name, operation, resource)
        
        if baseline is None:
            # No baseline available - record current as baseline
            self.record_test_result(test_name, operation, resource, current_duration, True)
            self.update_baseline(test_name, operation, resource)
            
            return RegressionResult(
                test_name=test_name,
                operation=operation,
                resource=resource,
                current_duration=current_duration,
                baseline_avg=current_duration,
                baseline_p95=current_duration,
                regression_detected=False,
                severity="none",
                change_percent=0.0,
                recommendation="Baseline established with current measurement"
            )
        
        # Calculate regression
        change_percent = ((current_duration - baseline.avg_duration) / baseline.avg_duration) * 100
        
        # Determine severity based on thresholds and percentiles
        regression_detected = False
        severity = "none"
        
        if current_duration > baseline.p99_duration:
            regression_detected = True
            severity = "critical"
        elif current_duration > baseline.p95_duration:
            regression_detected = True
            severity = "major" 
        elif change_percent > 25:  # 25% slower than average
            regression_detected = True
            severity = "minor"
        elif change_percent > 10:  # 10% slower than average
            severity = "minor"
        
        # Generate recommendation
        if severity == "critical":
            recommendation = f"CRITICAL: Performance degraded by {change_percent:.1f}%. Investigate immediately."
        elif severity == "major":
            recommendation = f"MAJOR: Performance degraded by {change_percent:.1f}%. Review recent changes."
        elif severity == "minor":
            recommendation = f"Minor performance degradation ({change_percent:.1f}%). Monitor trend."
        else:
            recommendation = "Performance within normal range."
        
        return RegressionResult(
            test_name=test_name,
            operation=operation,
            resource=resource,
            current_duration=current_duration,
            baseline_avg=baseline.avg_duration,
            baseline_p95=baseline.p95_duration,
            regression_detected=regression_detected,
            severity=severity,
            change_percent=change_percent,
            recommendation=recommendation
        )
    
    def analyze_test_run(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a complete test run for performance regressions"""
        regressions = []
        
        for result in test_results:
            if not result.get('success', False):
                continue
                
            regression = self.detect_regression(
                test_name=result.get('test_name', 'unknown'),
                operation=result.get('operation', 'unknown'),
                resource=result.get('resource', 'unknown'),
                current_duration=result.get('duration', 0.0)
            )
            
            regressions.append(regression)
            
            # Record the metric
            self.record_test_result(
                test_name=result.get('test_name', 'unknown'),
                operation=result.get('operation', 'unknown'),
                resource=result.get('resource', 'unknown'),
                duration=result.get('duration', 0.0),
                success=result.get('success', False),
                environment=result.get('environment', 'local')
            )
            
            # Update baseline if performance is good
            if not regression.regression_detected:
                self.update_baseline(
                    regression.test_name,
                    regression.operation,
                    regression.resource
                )
        
        # Summary statistics
        total_tests = len(regressions)
        critical_regressions = len([r for r in regressions if r.severity == "critical"])
        major_regressions = len([r for r in regressions if r.severity == "major"])
        minor_regressions = len([r for r in regressions if r.severity == "minor"])
        
        return {
            "total_tests_analyzed": total_tests,
            "regressions": {
                "critical": critical_regressions,
                "major": major_regressions,
                "minor": minor_regressions,
                "total": critical_regressions + major_regressions + minor_regressions
            },
            "regression_details": [asdict(r) for r in regressions if r.regression_detected],
            "all_results": [asdict(r) for r in regressions]
        }
    
    def get_performance_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get performance trends over time"""
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get average duration by day for trending
            cursor = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    operation,
                    resource,
                    AVG(duration) as avg_duration,
                    COUNT(*) as test_count
                FROM performance_metrics
                WHERE timestamp >= ? AND success = 1
                GROUP BY DATE(timestamp), operation, resource
                ORDER BY date DESC, operation, resource
            """, (cutoff_date,))
            
            trends = {}
            for row in cursor.fetchall():
                date, operation, resource, avg_duration, test_count = row
                key = f"{operation}_{resource}"
                
                if key not in trends:
                    trends[key] = {
                        "operation": operation,
                        "resource": resource,
                        "daily_averages": []
                    }
                
                trends[key]["daily_averages"].append({
                    "date": date,
                    "avg_duration": avg_duration,
                    "test_count": test_count
                })
            
            return {
                "period_days": days,
                "trends": trends
            }
    
    def cleanup_old_metrics(self, days_to_keep: int = 90):
        """Clean up old performance metrics"""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM performance_metrics 
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count