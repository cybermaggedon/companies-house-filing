import pytest
import time
import json
import threading
import concurrent.futures
from pathlib import Path
from statistics import mean, median, stdev
from dataclasses import dataclass
from typing import List, Dict, Any
import gc
import psutil
import os

from ch_filing.client import Client
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


@dataclass
class PerformanceMetrics:
    """Container for performance test metrics"""
    operation_name: str
    execution_times: List[float]
    memory_usage_mb: List[float]
    peak_memory_mb: float
    average_time: float
    median_time: float
    p95_time: float
    p99_time: float
    standard_deviation: float
    operations_per_second: float
    total_operations: int
    
    @classmethod
    def from_measurements(cls, operation_name: str, execution_times: List[float], memory_usage_mb: List[float] = None):
        if not execution_times:
            raise ValueError("No execution times provided")
        
        memory_usage_mb = memory_usage_mb or []
        peak_memory = max(memory_usage_mb) if memory_usage_mb else 0.0
        
        sorted_times = sorted(execution_times)
        n = len(sorted_times)
        
        return cls(
            operation_name=operation_name,
            execution_times=execution_times,
            memory_usage_mb=memory_usage_mb,
            peak_memory_mb=peak_memory,
            average_time=mean(execution_times),
            median_time=median(execution_times),
            p95_time=sorted_times[int(n * 0.95)] if n > 0 else 0.0,
            p99_time=sorted_times[int(n * 0.99)] if n > 0 else 0.0,
            standard_deviation=stdev(execution_times) if n > 1 else 0.0,
            operations_per_second=n / sum(execution_times) if sum(execution_times) > 0 else 0.0,
            total_operations=n
        )


class TestLoadTesting:
    """Load testing for the Companies House filing system"""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path"""
        return Path(__file__).parent.parent / "fixtures"
    
    @pytest.fixture
    def performance_state(self, tmp_path):
        """Create a test state optimized for performance testing"""
        config_file = tmp_path / "perf_config.json"
        config_data = {
            "presenter-id": "PERF_PRESENTER_123",
            "authentication": "PERF_AUTH_456",
            "company-number": "87654321",
            "company-name": "PERFORMANCE TEST COMPANY LIMITED",
            "company-authentication-code": "PERF1234",
            "company-type": "EW",
            "contact-name": "Performance Test Person",
            "contact-number": "07900 654321",
            "email": "performance@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "PERF001",
            "url": "http://localhost:9400/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "perf_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def performance_client(self, performance_state):
        """Create a client for performance testing"""
        return Client(performance_state)
    
    @pytest.fixture
    def sample_accounts_data(self, fixtures_dir):
        """Load sample accounts data for performance testing"""
        accounts_file = fixtures_dir / "sample_accounts.html"
        if accounts_file.exists():
            return accounts_file.read_text(encoding='utf-8')
        else:
            # Generate larger test data for performance testing
            return self._generate_large_accounts_data(50000)  # ~50KB
    
    def _generate_large_accounts_data(self, size_bytes: int) -> str:
        """Generate large accounts data for performance testing"""
        base_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:ixt="http://www.xbrl.org/2008/inlineXBRL/transformation"
      xmlns:uk-bus="http://xbrl.frc.org.uk/cd/2021-01-01/business"
      xmlns:uk-core="http://xbrl.frc.org.uk/fr/2021-01-01/core">
<head>
    <title>Performance Test Company - Annual Accounts</title>
    <ix:header>
        <ix:hidden>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityCurrentLegalName">PERFORMANCE TEST COMPANY LIMITED</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">87654321</ix:nonNumeric>
        </ix:hidden>
    </ix:header>
</head>
<body>
    <h1>PERFORMANCE TEST COMPANY LIMITED</h1>
    <table>
        <tr><th>Account</th><th>Amount</th></tr>"""
        
        # Generate table rows to reach target size
        row_template = '        <tr><td>Account {}</td><td><ix:nonFraction contextRef="period" name="uk-core:TotalCurrentAssets" unitRef="GBP">{}</ix:nonFraction></td></tr>\n'
        
        footer = """    </table>
    <p>Total Turnover: <ix:nonFraction contextRef="period" name="uk-core:Turnover" unitRef="GBP">1000000</ix:nonFraction></p>
</body>
</html>"""
        
        current_size = len(base_content) + len(footer)
        row_count = 0
        rows = ""
        
        while current_size < size_bytes:
            row = row_template.format(row_count, 10000 + row_count)
            rows += row
            current_size += len(row)
            row_count += 1
        
        return base_content + rows + footer
    
    def _measure_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    
    def _run_performance_test(self, operation_func, iterations: int = 100, warmup: int = 10) -> PerformanceMetrics:
        """Run a performance test with warmup and collect metrics"""
        gc.collect()  # Clean up before test
        
        # Warmup runs
        for _ in range(warmup):
            try:
                operation_func()
            except Exception:
                pass  # Ignore warmup errors
        
        execution_times = []
        memory_usage = []
        
        initial_memory = self._measure_memory_usage()
        
        for i in range(iterations):
            gc.collect()
            start_memory = self._measure_memory_usage()
            
            start_time = time.perf_counter()
            try:
                operation_func()
                end_time = time.perf_counter()
                execution_times.append(end_time - start_time)
            except Exception as e:
                # For tests that expect errors, still measure time
                end_time = time.perf_counter()
                execution_times.append(end_time - start_time)
            
            end_memory = self._measure_memory_usage()
            memory_usage.append(end_memory - initial_memory)
        
        operation_name = getattr(operation_func, '__name__', 'unknown_operation')
        return PerformanceMetrics.from_measurements(operation_name, execution_times, memory_usage)
    
    def test_company_data_creation_performance(self, performance_state):
        """Test performance of company data request creation"""
        def create_company_data():
            return CompanyData.create_request(performance_state)
        
        metrics = self._run_performance_test(create_company_data, iterations=1000, warmup=50)
        
        # Performance assertions
        assert metrics.average_time < 0.01, f"Company data creation too slow: {metrics.average_time:.4f}s avg"
        assert metrics.p95_time < 0.02, f"95th percentile too slow: {metrics.p95_time:.4f}s"
        assert metrics.operations_per_second > 100, f"Throughput too low: {metrics.operations_per_second:.1f} ops/sec"
        
        print(f"\nCompany Data Creation Performance:")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  Median time: {metrics.median_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  99th percentile: {metrics.p99_time:.4f}s")
        print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
    
    def test_envelope_creation_performance(self, performance_state):
        """Test performance of envelope creation"""
        content = CompanyData.create_request(performance_state)
        
        def create_envelope():
            return Envelope.create(performance_state, content, "CompanyDataRequest", "request")
        
        metrics = self._run_performance_test(create_envelope, iterations=500, warmup=25)
        
        # Performance assertions
        assert metrics.average_time < 0.02, f"Envelope creation too slow: {metrics.average_time:.4f}s avg"
        assert metrics.p95_time < 0.05, f"95th percentile too slow: {metrics.p95_time:.4f}s"
        assert metrics.operations_per_second > 50, f"Throughput too low: {metrics.operations_per_second:.1f} ops/sec"
        
        print(f"\nEnvelope Creation Performance:")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  Median time: {metrics.median_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  99th percentile: {metrics.p99_time:.4f}s")
        print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
    
    def test_form_submission_performance(self, performance_state, sample_accounts_data):
        """Test performance of form submission creation"""
        def create_form_submission():
            return Accounts.create_submission(performance_state, "perf_accounts.html", sample_accounts_data)
        
        metrics = self._run_performance_test(create_form_submission, iterations=100, warmup=10)
        
        # Performance assertions (more lenient due to base64 encoding)
        assert metrics.average_time < 0.1, f"Form submission creation too slow: {metrics.average_time:.4f}s avg"
        assert metrics.p95_time < 0.2, f"95th percentile too slow: {metrics.p95_time:.4f}s"
        assert metrics.operations_per_second > 10, f"Throughput too low: {metrics.operations_per_second:.1f} ops/sec"
        
        print(f"\nForm Submission Creation Performance:")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  Median time: {metrics.median_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  99th percentile: {metrics.p99_time:.4f}s")
        print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
        print(f"  Data size: {len(sample_accounts_data)} bytes")
    
    def test_state_operations_performance(self, performance_state):
        """Test performance of state operations (transaction IDs, submission IDs)"""
        def state_operations():
            tx_id = performance_state.get_next_tx_id()
            sub_id = performance_state.get_next_submission_id()
            cur_tx = performance_state.get_cur_tx_id()
            cur_sub = performance_state.get_cur_submission_id()
            return tx_id, sub_id, cur_tx, cur_sub
        
        metrics = self._run_performance_test(state_operations, iterations=1000, warmup=50)
        
        # Performance assertions
        assert metrics.average_time < 0.005, f"State operations too slow: {metrics.average_time:.4f}s avg"
        assert metrics.p95_time < 0.01, f"95th percentile too slow: {metrics.p95_time:.4f}s"
        assert metrics.operations_per_second > 200, f"Throughput too low: {metrics.operations_per_second:.1f} ops/sec"
        
        print(f"\nState Operations Performance:")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  Median time: {metrics.median_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  99th percentile: {metrics.p99_time:.4f}s")
        print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
    
    def test_concurrent_request_performance(self, performance_state):
        """Test performance under concurrent load"""
        def create_request():
            content = CompanyData.create_request(performance_state)
            envelope = Envelope.create(performance_state, content, "CompanyDataRequest", "request")
            return envelope
        
        # Test with different concurrency levels
        concurrency_levels = [1, 5, 10, 20]
        results = {}
        
        for concurrency in concurrency_levels:
            execution_times = []
            num_requests = 100
            
            def worker():
                start_time = time.perf_counter()
                try:
                    create_request()
                    end_time = time.perf_counter()
                    return end_time - start_time
                except Exception:
                    end_time = time.perf_counter()
                    return end_time - start_time
            
            start_total = time.perf_counter()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(worker) for _ in range(num_requests)]
                execution_times = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_total = time.perf_counter()
            total_time = end_total - start_total
            
            metrics = PerformanceMetrics.from_measurements(f"concurrent_{concurrency}", execution_times)
            results[concurrency] = {
                'metrics': metrics,
                'total_time': total_time,
                'actual_throughput': num_requests / total_time
            }
            
            print(f"\nConcurrency Level {concurrency}:")
            print(f"  Average time: {metrics.average_time:.4f}s")
            print(f"  95th percentile: {metrics.p95_time:.4f}s")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Actual throughput: {results[concurrency]['actual_throughput']:.1f} req/sec")
        
        # Verify that higher concurrency doesn't degrade performance too much
        baseline_throughput = results[1]['actual_throughput']
        for concurrency in [5, 10, 20]:
            current_throughput = results[concurrency]['actual_throughput']
            efficiency = current_throughput / baseline_throughput
            print(f"  Concurrency {concurrency} efficiency: {efficiency:.2f}")
            # Allow some degradation but not too much
            assert efficiency > 0.5, f"Performance degrades too much at concurrency {concurrency}: {efficiency:.2f}"
    
    @pytest.mark.slow
    def test_mock_server_load_performance(self, performance_state):
        """Test mock server performance under load"""
        with MockServer(
            port=9400,
            presenter_id="PERF_PRESENTER_123",
            authentication="PERF_AUTH_456",
            company_auth_code="PERF1234"
        ) as server:
            client = Client(performance_state)
            
            def make_request():
                content = CompanyData.create_request(performance_state)
                envelope = Envelope.create(performance_state, content, "CompanyDataRequest", "request")
                return client.call(performance_state, envelope)
            
            # Test server performance
            metrics = self._run_performance_test(make_request, iterations=50, warmup=5)
            
            # Performance assertions for network requests
            assert metrics.average_time < 0.1, f"Server requests too slow: {metrics.average_time:.4f}s avg"
            assert metrics.p95_time < 0.2, f"95th percentile too slow: {metrics.p95_time:.4f}s"
            assert metrics.operations_per_second > 10, f"Server throughput too low: {metrics.operations_per_second:.1f} ops/sec"
            
            print(f"\nMock Server Performance:")
            print(f"  Average time: {metrics.average_time:.4f}s")
            print(f"  Median time: {metrics.median_time:.4f}s")
            print(f"  95th percentile: {metrics.p95_time:.4f}s")
            print(f"  99th percentile: {metrics.p99_time:.4f}s")
            print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
            print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
    
    def test_large_data_handling_performance(self, performance_state):
        """Test performance with large accounts data"""
        data_sizes = [10000, 50000, 100000, 500000]  # Various sizes in bytes
        
        for size in data_sizes:
            large_data = self._generate_large_accounts_data(size)
            
            def create_large_submission():
                return Accounts.create_submission(performance_state, f"large_{size}.html", large_data)
            
            metrics = self._run_performance_test(create_large_submission, iterations=10, warmup=2)
            
            print(f"\nLarge Data Performance ({size} bytes):")
            print(f"  Average time: {metrics.average_time:.4f}s")
            print(f"  95th percentile: {metrics.p95_time:.4f}s")
            print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
            print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
            print(f"  Throughput: {size / metrics.average_time / 1024:.1f} KB/s")
            
            # Performance should scale reasonably with data size
            expected_max_time = size / 10000 * 0.01  # ~0.01s per 10KB
            assert metrics.average_time < expected_max_time, f"Large data handling too slow for {size} bytes"
    
    @pytest.mark.slow
    def test_sustained_load_performance(self, performance_state):
        """Test performance under sustained load over time"""
        duration_seconds = 30
        request_interval = 0.1  # 10 requests per second target
        
        execution_times = []
        memory_usage = []
        start_test = time.perf_counter()
        last_request = start_test
        
        while time.perf_counter() - start_test < duration_seconds:
            current_time = time.perf_counter()
            if current_time - last_request >= request_interval:
                gc.collect()
                memory_before = self._measure_memory_usage()
                
                request_start = time.perf_counter()
                try:
                    content = CompanyData.create_request(performance_state)
                    envelope = Envelope.create(performance_state, content, "CompanyDataRequest", "request")
                    request_end = time.perf_counter()
                    execution_times.append(request_end - request_start)
                except Exception:
                    request_end = time.perf_counter()
                    execution_times.append(request_end - request_start)
                
                memory_after = self._measure_memory_usage()
                memory_usage.append(memory_after)
                last_request = current_time
            
            time.sleep(0.001)  # Small sleep to prevent CPU spinning
        
        actual_duration = time.perf_counter() - start_test
        metrics = PerformanceMetrics.from_measurements("sustained_load", execution_times, memory_usage)
        
        print(f"\nSustained Load Performance ({actual_duration:.1f}s):")
        print(f"  Total requests: {len(execution_times)}")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  Actual rate: {len(execution_times) / actual_duration:.1f} req/sec")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")
        print(f"  Memory growth: {max(memory_usage) - min(memory_usage):.2f}MB")
        
        # Verify no significant performance degradation over time
        first_half = execution_times[:len(execution_times)//2]
        second_half = execution_times[len(execution_times)//2:]
        
        if first_half and second_half:
            first_avg = mean(first_half)
            second_avg = mean(second_half)
            degradation = (second_avg - first_avg) / first_avg
            
            print(f"  Performance degradation: {degradation:.2%}")
            assert degradation < 0.5, f"Performance degraded too much over time: {degradation:.2%}"
            
            # Check for memory leaks
            memory_growth = max(memory_usage) - min(memory_usage)
            assert memory_growth < 50, f"Potential memory leak detected: {memory_growth:.2f}MB growth"
    
    def test_error_condition_performance(self, performance_state):
        """Test performance when errors occur"""
        # Test with invalid data that will cause errors
        invalid_state = State(performance_state.config_file, performance_state.state_file)
        invalid_state.config["company-number"] = ""  # Invalid company number
        
        def create_invalid_request():
            try:
                content = CompanyData.create_request(invalid_state)
                envelope = Envelope.create(invalid_state, content, "CompanyDataRequest", "request")
                return envelope
            except Exception:
                pass  # Expected errors
        
        metrics = self._run_performance_test(create_invalid_request, iterations=100, warmup=10)
        
        # Error handling shouldn't be significantly slower than normal operations
        assert metrics.average_time < 0.02, f"Error handling too slow: {metrics.average_time:.4f}s avg"
        
        print(f"\nError Condition Performance:")
        print(f"  Average time: {metrics.average_time:.4f}s")
        print(f"  95th percentile: {metrics.p95_time:.4f}s")
        print(f"  Operations/sec: {metrics.operations_per_second:.1f}")
        print(f"  Peak memory: {metrics.peak_memory_mb:.2f}MB")