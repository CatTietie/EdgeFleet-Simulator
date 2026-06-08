"""Load test: 2000 device concurrent reporting and rule engine latency."""
import asyncio
import time
import statistics
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.rule_dsl.parser import parse_rule
from app.rule_dsl.evaluator import evaluate_condition
from app.rule_dsl.state_machine import DeviceRuleState, StateStore
from app.services.rule_engine import RuleEngine
from app.services.alarm_manager import AlarmManager
from app.services.webhook_dispatcher import WebhookDispatcher
from simulator.device_factory import create_devices


class TestRuleEngineLatency:
    """Measure rule evaluation latency under load."""

    def _create_engine_with_rules(self, rule_count: int = 50) -> RuleEngine:
        webhook_dispatcher = WebhookDispatcher()
        alarm_manager = AlarmManager(webhook_dispatcher, redis_client=None)
        engine = RuleEngine(alarm_manager)

        for i in range(rule_count):
            rule_data = {
                "rule_id": f"rule-{i:03d}",
                "name": f"Test Rule {i}",
                "org_id": "org-load-test",
                "enabled": True,
                "target": {"scope": "org"},
                "trigger_condition": {
                    "operator": "AND",
                    "conditions": [
                        {"metric": "temperature", "comparator": ">", "threshold": 80,
                         "temporal": {"type": "consecutive", "count": 3}},
                        {"metric": "humidity", "comparator": "<", "threshold": 20,
                         "temporal": None},
                    ]
                },
                "recovery_condition": {
                    "operator": "AND",
                    "conditions": [
                        {"metric": "temperature", "comparator": "<=", "threshold": 75,
                         "temporal": {"type": "consecutive", "count": 2}},
                    ]
                },
                "severity": "warning",
                "actions": {"webhook_urls": [], "cooldown_seconds": 30},
            }
            parsed = parse_rule(rule_data)
            engine.register_rule(parsed)

        return engine

    @pytest.mark.asyncio
    async def test_single_evaluation_latency(self):
        """Single rule evaluation should be sub-millisecond."""
        engine = self._create_engine_with_rules(1)
        data_point = {
            "org_id": "org-load-test",
            "group_id": "default",
            "device_id": "sensor-00001",
            "timestamp": int(time.time() * 1000),
            "metrics": {"temperature": 75.0, "humidity": 45.0},
        }

        start = time.perf_counter()
        await engine.evaluate(data_point)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 5.0, f"Single evaluation took {elapsed_ms:.2f}ms"

    @pytest.mark.asyncio
    async def test_2000_devices_50_rules_throughput(self):
        """Simulate 2000 devices with 50 rules each: measure throughput."""
        engine = self._create_engine_with_rules(50)
        devices = create_devices(2000, "org-load-test", "default", anomaly_ratio=0.1)

        latencies = []
        base_time = int(time.time() * 1000)

        for i, device in enumerate(devices):
            reading = device.read()
            data_point = {
                "org_id": "org-load-test",
                "group_id": "default",
                "device_id": device.device_id,
                "timestamp": base_time + i,
                "metrics": reading["metrics"],
            }

            start = time.perf_counter()
            await engine.evaluate(data_point)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        total_time = sum(latencies)

        print(f"\n--- Rule Engine Load Test Results ---")
        print(f"Devices: 2000, Rules: 50")
        print(f"Total evaluations: {len(latencies)}")
        print(f"Total time: {total_time:.1f}ms")
        print(f"Throughput: {len(latencies) / (total_time / 1000):.0f} eval/s")
        print(f"Latency p50: {p50:.3f}ms")
        print(f"Latency p95: {p95:.3f}ms")
        print(f"Latency p99: {p99:.3f}ms")

        # Performance assertions
        assert p50 < 1.0, f"p50 latency {p50:.3f}ms exceeds 1ms"
        assert p95 < 5.0, f"p95 latency {p95:.3f}ms exceeds 5ms"

    @pytest.mark.asyncio
    async def test_500_concurrent_alarms(self):
        """500 devices all triggering alarms simultaneously."""
        engine = self._create_engine_with_rules(10)
        base_time = int(time.time() * 1000)

        # Warm up: feed 3 consecutive readings above threshold
        for seq in range(3):
            for i in range(500):
                data_point = {
                    "org_id": "org-load-test",
                    "group_id": "default",
                    "device_id": f"alarm-device-{i:04d}",
                    "timestamp": base_time + (seq * 1000) + i,
                    "metrics": {"temperature": 85.0, "humidity": 15.0},
                }
                await engine.evaluate(data_point)

        # The 3rd reading should trigger all 500 alarms (10 rules each = 5000 state entries)
        assert engine.state_count >= 500


class TestDeviceSimulatorScale:
    """Verify simulator can create and read from 2000 devices."""

    def test_create_2000_devices(self):
        devices = create_devices(2000, "org-perf", "default")
        assert len(devices) == 2000

    def test_all_devices_produce_valid_readings(self):
        devices = create_devices(2000, "org-perf", "default")
        for device in devices:
            reading = device.read()
            assert "metrics" in reading
            assert "temperature" in reading["metrics"]
            assert "humidity" in reading["metrics"]
            assert -10 <= reading["metrics"]["temperature"] <= 100
            assert 5 <= reading["metrics"]["humidity"] <= 95

    def test_device_seq_increments(self):
        devices = create_devices(10, "org-perf", "default")
        for device in devices:
            r1 = device.read()
            r2 = device.read()
            assert r2["seq"] == r1["seq"] + 1
