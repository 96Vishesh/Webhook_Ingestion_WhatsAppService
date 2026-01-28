"""
Prometheus-style metrics collection.
"""
from collections import defaultdict
from threading import Lock
from typing import Optional


class MetricsCollector:
    """Thread-safe metrics collector for Prometheus-style metrics."""
    
    # Latency histogram buckets in milliseconds
    LATENCY_BUCKETS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    
    def __init__(self):
        self._lock = Lock()
        
        # Counters: http_requests_total{path, status}
        self._http_requests: dict[tuple[str, int], int] = defaultdict(int)
        
        # Counters: webhook_requests_total{result}
        self._webhook_requests: dict[str, int] = defaultdict(int)
        
        # Histogram: request_latency_ms
        self._latency_buckets: dict[float, int] = {b: 0 for b in self.LATENCY_BUCKETS}
        self._latency_buckets[float("inf")] = 0
        self._latency_count = 0
        self._latency_sum = 0.0
    
    def inc_http_requests(self, path: str, status: int) -> None:
        """Increment HTTP requests counter."""
        with self._lock:
            self._http_requests[(path, status)] += 1
    
    def inc_webhook_requests(self, result: str) -> None:
        """Increment webhook requests counter."""
        with self._lock:
            self._webhook_requests[result] += 1
    
    def observe_latency(self, latency_ms: float) -> None:
        """Record a latency observation in the histogram."""
        with self._lock:
            self._latency_count += 1
            self._latency_sum += latency_ms
            
            for bucket in self.LATENCY_BUCKETS:
                if latency_ms <= bucket:
                    self._latency_buckets[bucket] += 1
            self._latency_buckets[float("inf")] += 1
    
    def format_prometheus(self) -> str:
        """Format metrics in Prometheus exposition format."""
        lines = []
        
        with self._lock:
            # HTTP requests counter
            lines.append("# HELP http_requests_total Total HTTP requests")
            lines.append("# TYPE http_requests_total counter")
            for (path, status), count in sorted(self._http_requests.items()):
                lines.append(f'http_requests_total{{path="{path}",status="{status}"}} {count}')
            
            # Webhook requests counter
            lines.append("")
            lines.append("# HELP webhook_requests_total Total webhook requests by result")
            lines.append("# TYPE webhook_requests_total counter")
            for result, count in sorted(self._webhook_requests.items()):
                lines.append(f'webhook_requests_total{{result="{result}"}} {count}')
            
            # Latency histogram
            lines.append("")
            lines.append("# HELP request_latency_ms Request latency in milliseconds")
            lines.append("# TYPE request_latency_ms histogram")
            
            cumulative = 0
            for bucket in self.LATENCY_BUCKETS:
                cumulative += self._latency_buckets[bucket]
                lines.append(f'request_latency_ms_bucket{{le="{bucket}"}} {cumulative}')
            
            lines.append(f'request_latency_ms_bucket{{le="+Inf"}} {self._latency_buckets[float("inf")]}')
            lines.append(f"request_latency_ms_count {self._latency_count}")
            lines.append(f"request_latency_ms_sum {self._latency_sum:.2f}")
        
        return "\n".join(lines)


# Global metrics instance
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
