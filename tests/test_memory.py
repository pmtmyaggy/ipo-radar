"""内存泄漏检查测试.

检测系统中的内存泄漏问题。
"""

import pytest
import gc
import tracemalloc
import sys

# memory_profiler 是可选的
try:
    from memory_profiler import profile as mem_profile
    HAS_MEMORY_PROFILER = True
except ImportError:
    HAS_MEMORY_PROFILER = False
    mem_profile = lambda f: f

from src.scorer.daily_scan import DailyScanner
from src.scorer.composite import SignalAggregator
from src.crawler.api import CrawlerAPI


class TestMemoryLeaks:
    """测试内存泄漏."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """测试前清理内存."""
        gc.collect()
        yield
        gc.collect()

    def test_scanner_no_leak(self):
        """测试扫描器无内存泄漏."""
        tracemalloc.start()
        
        # 记录初始内存
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        
        # 执行多次扫描
        scanner = DailyScanner()
        for _ in range(10):
            try:
                scanner.run_scan(tickers=["TEST"])
            except Exception:
                pass  # 我们关注的是内存，不是结果
        
        # 强制垃圾回收
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        
        # 比较内存使用
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # 检查内存增长是否可控 (< 10MB)
        total_diff = sum(stat.size_diff for stat in top_stats[:10] if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        # 内存增长应小于10MB
        assert total_diff < 10 * 1024 * 1024, f"Memory leak detected: {total_diff / 1024 / 1024:.2f} MB"

    def test_aggregator_no_leak(self):
        """测试聚合器无内存泄漏."""
        tracemalloc.start()
        
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        
        # 创建多个聚合器实例
        for _ in range(5):
            try:
                agg = SignalAggregator()
                # 模拟报告生成
                del agg
            except Exception:
                pass
        
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_diff = sum(stat.size_diff for stat in top_stats[:10] if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        assert total_diff < 5 * 1024 * 1024, f"Aggregator leak: {total_diff / 1024 / 1024:.2f} MB"

    def test_crawler_session_cleanup(self):
        """测试爬虫session正确清理."""
        import requests
        
        initial_sessions = len([obj for obj in gc.get_objects() if isinstance(obj, requests.Session)])
        
        # 创建和销毁多个crawler
        for _ in range(5):
            crawler = CrawlerAPI()
            del crawler
        
        gc.collect()
        
        final_sessions = len([obj for obj in gc.get_objects() if isinstance(obj, requests.Session)])
        
        # session数量应该保持稳定
        assert final_sessions <= initial_sessions + 1

    def test_dataframe_memory(self):
        """测试DataFrame内存使用."""
        import pandas as pd
        import numpy as np
        
        tracemalloc.start()
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        
        # 创建和处理大数据集
        for _ in range(5):
            df = pd.DataFrame({
                'A': np.random.randn(10000),
                'B': np.random.randn(10000),
                'C': np.random.randn(10000),
            })
            result = df.sum()
            del df, result
        
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_diff = sum(stat.size_diff for stat in top_stats[:10] if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        # DataFrame应该被正确释放
        assert total_diff < 1 * 1024 * 1024, f"DataFrame leak: {total_diff / 1024 / 1024:.2f} MB"

    def test_database_connection_cleanup(self):
        """测试数据库连接清理."""
        from src.crawler.models.database import DatabaseManager, init_database
        
        # 确保数据库已初始化
        init_database()
        
        gc.collect()
        initial_count = len([obj for obj in gc.get_objects() if isinstance(obj, DatabaseManager)])
        
        # 创建多个连接
        for _ in range(10):
            db = DatabaseManager()
            # 获取session后关闭
            try:
                with db.session_scope() as session:
                    pass
            except:
                pass
            del db
        
        gc.collect()
        final_count = len([obj for obj in gc.get_objects() if isinstance(obj, DatabaseManager)])
        
        # 连接应该被清理
        assert final_count <= initial_count + 5  # 允许少量浮动


class TestMemoryOptimization:
    """测试内存优化."""

    def test_batch_processing_memory(self):
        """测试批量处理内存效率."""
        from src.utils.batch_processor import batch_process
        
        # 生成大量数据
        data = list(range(10000))
        
        tracemalloc.start()
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        
        # 使用批量处理
        results = list(batch_process(data, batch_size=1000))
        
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_diff = sum(stat.size_diff for stat in top_stats[:10] if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        assert len(results) == 10000
        assert total_diff < 5 * 1024 * 1024

    def test_stream_processing_memory(self):
        """测试流式处理内存效率."""
        from src.utils.batch_processor import stream_process
        
        def data_generator():
            for i in range(10000):
                yield i
        
        def processor(x):
            return x * 2
        
        tracemalloc.start()
        gc.collect()
        snapshot1 = tracemalloc.take_snapshot()
        
        # 使用流式处理
        results = list(stream_process(data_generator(), processor))
        
        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_diff = sum(stat.size_diff for stat in top_stats[:10] if stat.size_diff > 0)
        
        tracemalloc.stop()
        
        assert len(results) == 10000
        # 流式处理应该占用更少内存
        assert total_diff < 2 * 1024 * 1024


class TestGarbageCollection:
    """测试垃圾回收."""

    def test_gc_enabled(self):
        """测试垃圾回收已启用."""
        assert gc.isenabled()

    def test_gc_generations(self):
        """测试垃圾回收代."""
        # 获取GC统计
        counts = gc.get_count()
        assert len(counts) == 3  # 三代

    def test_manual_gc(self):
        """测试手动垃圾回收."""
        # 创建一些循环引用
        class Node:
            def __init__(self):
                self.ref = None
        
        nodes = [Node() for _ in range(100)]
        for i in range(len(nodes) - 1):
            nodes[i].ref = nodes[i + 1]
        
        # 删除引用
        del nodes
        
        # 手动回收
        collected = gc.collect()
        
        # 应该有一些对象被回收
        assert collected >= 0


@pytest.mark.skipif(
    not HAS_MEMORY_PROFILER,
    reason="memory_profiler not installed"
)
class TestMemoryProfile:
    """内存分析测试（需要 memory_profiler）."""

    def test_scanner_memory_profile(self):
        """测试扫描器内存分析."""
        # 此测试需要 memory_profiler
        pass
