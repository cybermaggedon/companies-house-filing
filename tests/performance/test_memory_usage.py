import pytest
import gc
import psutil
import os
import threading
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import tracemalloc
import weakref

from ch_filing.client import Client
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: float
    rss_mb: float
    vms_mb: float
    cpu_percent: float
    operation: str
    
    @classmethod
    def capture(cls, operation: str = "unknown") -> 'MemorySnapshot':
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return cls(
            timestamp=time.time(),
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            cpu_percent=process.cpu_percent(),
            operation=operation
        )


class MemoryTracker:
    """Track memory usage during operations"""
    
    def __init__(self, interval_seconds: float = 0.1):
        self.interval = interval_seconds
        self.snapshots: List[MemorySnapshot] = []
        self.tracking = False
        self._thread: Optional[threading.Thread] = None
    
    def start_tracking(self):
        """Start memory tracking in background thread"""
        self.tracking = True
        self.snapshots.clear()
        self._thread = threading.Thread(target=self._track_loop, daemon=True)
        self._thread.start()
    
    def stop_tracking(self):
        """Stop memory tracking"""
        self.tracking = False
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def add_snapshot(self, operation: str):
        """Add a manual snapshot"""
        self.snapshots.append(MemorySnapshot.capture(operation))
    
    def _track_loop(self):
        """Background tracking loop"""
        while self.tracking:
            self.snapshots.append(MemorySnapshot.capture("background"))
            time.sleep(self.interval)
    
    def get_peak_memory(self) -> float:
        """Get peak RSS memory usage in MB"""
        return max(s.rss_mb for s in self.snapshots) if self.snapshots else 0.0
    
    def get_memory_growth(self) -> float:
        """Get memory growth from start to end in MB"""
        if len(self.snapshots) < 2:
            return 0.0
        return self.snapshots[-1].rss_mb - self.snapshots[0].rss_mb
    
    def get_average_memory(self) -> float:
        """Get average memory usage in MB"""
        return sum(s.rss_mb for s in self.snapshots) / len(self.snapshots) if self.snapshots else 0.0


class TestMemoryUsage:
    """Memory usage and response time tests"""
    
    @pytest.fixture
    def memory_state(self, tmp_path):
        """Create a test state for memory testing"""
        config_file = tmp_path / "memory_config.json"
        config_data = {
            "presenter-id": "MEMORY_PRESENTER_123",
            "authentication": "MEMORY_AUTH_456",
            "company-number": "11223344",
            "company-name": "MEMORY TEST COMPANY LIMITED",
            "company-authentication-code": "MEM1234",
            "company-type": "EW",
            "contact-name": "Memory Test Person",
            "contact-number": "07900 112233",
            "email": "memory@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "MEM001",
            "url": "http://localhost:9401/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "memory_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def memory_tracker(self):
        """Create a memory tracker"""
        tracker = MemoryTracker(interval_seconds=0.05)
        yield tracker
        tracker.stop_tracking()
    
    def test_basic_memory_usage(self, memory_state, memory_tracker):
        """Test basic memory usage for core operations"""
        memory_tracker.start_tracking()
        gc.collect()
        memory_tracker.add_snapshot("start")
        
        # Create company data request
        content = CompanyData.create_request(memory_state)
        memory_tracker.add_snapshot("company_data_created")
        
        # Create envelope
        envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
        memory_tracker.add_snapshot("envelope_created")
        
        # Create client
        client = Client(memory_state)
        memory_tracker.add_snapshot("client_created")
        
        # Clean up
        del content, envelope, client
        gc.collect()
        memory_tracker.add_snapshot("cleanup")
        
        memory_tracker.stop_tracking()
        
        # Analyze memory usage
        peak_memory = memory_tracker.get_peak_memory()
        memory_growth = memory_tracker.get_memory_growth()
        
        print(f"\nBasic Memory Usage:")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Average memory: {memory_tracker.get_average_memory():.2f}MB")
        
        # Memory usage should be reasonable
        assert peak_memory < 100, f"Peak memory usage too high: {peak_memory:.2f}MB"
        assert abs(memory_growth) < 10, f"Significant memory growth detected: {memory_growth:.2f}MB"
    
    def test_large_data_memory_usage(self, memory_state, memory_tracker):
        """Test memory usage with large accounts data"""
        memory_tracker.start_tracking()
        gc.collect()
        memory_tracker.add_snapshot("start")
        
        # Generate large accounts data (1MB)
        large_data = self._generate_large_accounts_data(1024 * 1024)
        memory_tracker.add_snapshot("large_data_generated")
        
        # Create form submission
        submission = Accounts.create_submission(memory_state, "large_test.html", large_data)
        memory_tracker.add_snapshot("form_submission_created")
        
        # Create envelope
        envelope = Envelope.create(memory_state, submission, "Accounts", "request")
        memory_tracker.add_snapshot("envelope_created")
        
        # Clean up
        del large_data, submission, envelope
        gc.collect()
        memory_tracker.add_snapshot("cleanup")
        
        memory_tracker.stop_tracking()
        
        peak_memory = memory_tracker.get_peak_memory()
        memory_growth = memory_tracker.get_memory_growth()
        
        print(f"\nLarge Data Memory Usage:")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Average memory: {memory_tracker.get_average_memory():.2f}MB")
        
        # Large data should use more memory but not excessively
        assert peak_memory < 200, f"Peak memory usage too high for large data: {peak_memory:.2f}MB"
        assert abs(memory_growth) < 20, f"Significant memory growth with large data: {memory_growth:.2f}MB"
    
    def test_repeated_operations_memory_leak(self, memory_state, memory_tracker):
        """Test for memory leaks during repeated operations"""
        memory_tracker.start_tracking()
        gc.collect()
        memory_tracker.add_snapshot("start")
        
        # Perform many operations
        for i in range(100):
            content = CompanyData.create_request(memory_state)
            envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
            client = Client(memory_state)
            
            # Clean up explicitly
            del content, envelope, client
            
            if i % 20 == 0:
                gc.collect()
                memory_tracker.add_snapshot(f"iteration_{i}")
        
        gc.collect()
        memory_tracker.add_snapshot("final_cleanup")
        memory_tracker.stop_tracking()
        
        peak_memory = memory_tracker.get_peak_memory()
        memory_growth = memory_tracker.get_memory_growth()
        
        print(f"\nRepeated Operations Memory:")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Average memory: {memory_tracker.get_average_memory():.2f}MB")
        
        # Check for significant memory leaks
        assert abs(memory_growth) < 50, f"Potential memory leak detected: {memory_growth:.2f}MB growth"
        
        # Analyze growth trend
        snapshots = [s for s in memory_tracker.snapshots if s.operation.startswith("iteration_")]
        if len(snapshots) >= 3:
            first_third = snapshots[:len(snapshots)//3]
            last_third = snapshots[-len(snapshots)//3:]
            
            avg_first = sum(s.rss_mb for s in first_third) / len(first_third)
            avg_last = sum(s.rss_mb for s in last_third) / len(last_third)
            trend = avg_last - avg_first
            
            print(f"  Memory trend: {trend:.2f}MB")
            assert abs(trend) < 30, f"Concerning memory trend: {trend:.2f}MB"
    
    def test_concurrent_memory_usage(self, memory_state, memory_tracker):
        """Test memory usage under concurrent load"""
        import concurrent.futures
        
        memory_tracker.start_tracking()
        gc.collect()
        memory_tracker.add_snapshot("start")
        
        def worker_task(worker_id: int) -> int:
            """Worker task that creates and processes requests"""
            operations = 0
            for _ in range(10):
                content = CompanyData.create_request(memory_state)
                envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
                client = Client(memory_state)
                operations += 3
                
                # Clean up
                del content, envelope, client
            
            return operations
        
        # Run concurrent workers
        total_operations = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            memory_tracker.add_snapshot("workers_started")
            
            futures = [executor.submit(worker_task, i) for i in range(5)]
            for future in concurrent.futures.as_completed(futures):
                total_operations += future.result()
            
            memory_tracker.add_snapshot("workers_completed")
        
        gc.collect()
        memory_tracker.add_snapshot("final_cleanup")
        memory_tracker.stop_tracking()
        
        peak_memory = memory_tracker.get_peak_memory()
        memory_growth = memory_tracker.get_memory_growth()
        
        print(f"\nConcurrent Memory Usage:")
        print(f"  Total operations: {total_operations}")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Average memory: {memory_tracker.get_average_memory():.2f}MB")
        print(f"  Memory per operation: {peak_memory / total_operations:.4f}MB")
        
        # Concurrent operations shouldn't use excessive memory
        assert peak_memory < 150, f"Peak memory too high for concurrent operations: {peak_memory:.2f}MB"
        assert abs(memory_growth) < 30, f"Significant memory growth in concurrent test: {memory_growth:.2f}MB"
    
    def test_memory_usage_with_tracemalloc(self, memory_state):
        """Test memory usage with detailed allocation tracking"""
        tracemalloc.start()
        
        # Baseline measurement
        gc.collect()
        snapshot_start = tracemalloc.take_snapshot()
        
        # Perform operations
        objects = []
        for i in range(50):
            content = CompanyData.create_request(memory_state)
            envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
            client = Client(memory_state)
            objects.extend([content, envelope, client])
        
        snapshot_after = tracemalloc.take_snapshot()
        
        # Analyze top allocations
        top_stats = snapshot_after.compare_to(snapshot_start, 'lineno')
        
        print(f"\nTop Memory Allocations:")
        for index, stat in enumerate(top_stats[:10]):
            print(f"  {index + 1}. {stat}")
        
        # Clean up and measure
        del objects
        gc.collect()
        snapshot_cleanup = tracemalloc.take_snapshot()
        
        cleanup_stats = snapshot_cleanup.compare_to(snapshot_start, 'lineno')
        total_allocated = sum(stat.size_diff for stat in cleanup_stats if stat.size_diff > 0)
        total_freed = sum(abs(stat.size_diff) for stat in cleanup_stats if stat.size_diff < 0)
        
        print(f"\nMemory Allocation Summary:")
        print(f"  Total allocated: {total_allocated / 1024 / 1024:.2f}MB")
        print(f"  Total freed: {total_freed / 1024 / 1024:.2f}MB")
        print(f"  Net growth: {(total_allocated - total_freed) / 1024 / 1024:.2f}MB")
        
        tracemalloc.stop()
        
        # Verify reasonable memory behavior
        net_growth_mb = (total_allocated - total_freed) / 1024 / 1024
        assert abs(net_growth_mb) < 10, f"Significant net memory growth: {net_growth_mb:.2f}MB"
    
    def test_response_time_under_memory_pressure(self, memory_state):
        """Test response times when system is under memory pressure"""
        import time
        
        # Create memory pressure by allocating large objects
        memory_hogs = []
        try:
            # Allocate memory in chunks
            for _ in range(5):
                memory_hogs.append(bytearray(50 * 1024 * 1024))  # 50MB each
            
            gc.collect()
            
            # Measure response times under pressure
            times = []
            for _ in range(20):
                start_time = time.perf_counter()
                content = CompanyData.create_request(memory_state)
                envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
                end_time = time.perf_counter()
                
                times.append(end_time - start_time)
                del content, envelope
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            print(f"\nResponse Times Under Memory Pressure:")
            print(f"  Average time: {avg_time:.4f}s")
            print(f"  Max time: {max_time:.4f}s")
            print(f"  Memory pressure: ~{len(memory_hogs) * 50}MB allocated")
            
            # Response times shouldn't degrade too much under memory pressure
            assert avg_time < 0.1, f"Average response time too slow under pressure: {avg_time:.4f}s"
            assert max_time < 0.2, f"Max response time too slow under pressure: {max_time:.4f}s"
            
        finally:
            # Clean up memory pressure
            del memory_hogs
            gc.collect()
    
    def test_object_lifecycle_and_garbage_collection(self, memory_state):
        """Test object lifecycle and garbage collection behavior"""
        weak_refs = []
        
        # Create objects and weak references
        for i in range(20):
            content = CompanyData.create_request(memory_state)
            envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
            client = Client(memory_state)
            
            # Create weak references to track object lifecycle
            weak_refs.extend([
                weakref.ref(content),
                weakref.ref(envelope),
                weakref.ref(client)
            ])
            
            # Objects go out of scope here
        
        # Force garbage collection
        gc.collect()
        
        # Check how many objects were collected
        alive_count = sum(1 for ref in weak_refs if ref() is not None)
        collected_count = len(weak_refs) - alive_count
        collection_rate = collected_count / len(weak_refs)
        
        print(f"\nObject Lifecycle:")
        print(f"  Total objects created: {len(weak_refs)}")
        print(f"  Objects collected: {collected_count}")
        print(f"  Objects still alive: {alive_count}")
        print(f"  Collection rate: {collection_rate:.2%}")
        
        # Most objects should be collected
        assert collection_rate > 0.8, f"Poor garbage collection rate: {collection_rate:.2%}"
    
    @pytest.mark.slow
    def test_long_running_memory_stability(self, memory_state, memory_tracker):
        """Test memory stability over extended operation"""
        memory_tracker.start_tracking()
        gc.collect()
        memory_tracker.add_snapshot("start")
        
        # Run for extended period
        start_time = time.time()
        operation_count = 0
        
        while time.time() - start_time < 60:  # Run for 1 minute
            content = CompanyData.create_request(memory_state)
            envelope = Envelope.create(memory_state, content, "CompanyDataRequest", "request")
            client = Client(memory_state)
            
            operation_count += 1
            
            # Periodic cleanup
            if operation_count % 50 == 0:
                gc.collect()
                memory_tracker.add_snapshot(f"operations_{operation_count}")
            
            del content, envelope, client
            time.sleep(0.1)  # Small delay to simulate real usage
        
        gc.collect()
        memory_tracker.add_snapshot("final")
        memory_tracker.stop_tracking()
        
        peak_memory = memory_tracker.get_peak_memory()
        memory_growth = memory_tracker.get_memory_growth()
        duration = time.time() - start_time
        
        print(f"\nLong Running Memory Stability:")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Operations: {operation_count}")
        print(f"  Operations/sec: {operation_count / duration:.1f}")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory growth: {memory_growth:.2f}MB")
        print(f"  Memory per operation: {peak_memory / operation_count:.4f}MB")
        
        # Memory should remain stable over long runs
        assert abs(memory_growth) < 20, f"Memory grew too much over long run: {memory_growth:.2f}MB"
        
        # Check for memory stability trend
        periodic_snapshots = [s for s in memory_tracker.snapshots if s.operation.startswith("operations_")]
        if len(periodic_snapshots) >= 4:
            memories = [s.rss_mb for s in periodic_snapshots]
            # Calculate trend (simple linear regression slope)
            n = len(memories)
            x_mean = (n - 1) / 2
            y_mean = sum(memories) / n
            
            slope = sum((i - x_mean) * (memories[i] - y_mean) for i in range(n))
            slope = slope / sum((i - x_mean) ** 2 for i in range(n))
            
            print(f"  Memory trend slope: {slope:.4f}MB per checkpoint")
            assert abs(slope) < 1.0, f"Concerning memory trend: {slope:.4f}MB per checkpoint"
    
    def _generate_large_accounts_data(self, size_bytes: int) -> str:
        """Generate large accounts data for memory testing"""
        base_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>Memory Test Accounts</title></head>
<body><h1>MEMORY TEST COMPANY LIMITED</h1><table>"""
        
        footer = "</table></body></html>"
        
        row_template = '<tr><td>Account {}</td><td>{}</td></tr>'
        current_size = len(base_content) + len(footer)
        rows = []
        row_count = 0
        
        while current_size < size_bytes:
            row = row_template.format(row_count, 10000 + row_count)
            rows.append(row)
            current_size += len(row)
            row_count += 1
        
        return base_content + ''.join(rows) + footer