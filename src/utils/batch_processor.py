"""批量处理优化模块.

提供批量处理和流式处理功能，优化大数据集处理性能。
"""

import logging
from typing import Iterator, Callable, TypeVar, List, Optional
from functools import wraps
import gc

logger = logging.getLogger(__name__)

T = TypeVar('T')


def batch_process(
    items: List[T],
    batch_size: int = 100,
    processor: Callable[[List[T]], List[T]] = None,
    enable_gc: bool = True,
) -> Iterator[T]:
    """批量处理数据.
    
    Args:
        items: 待处理的数据列表
        batch_size: 每批处理的数量
        processor: 处理函数，接收批次数据返回处理结果
        enable_gc: 是否启用垃圾回收
        
    Yields:
        处理后的单个数据项
    
    Example:
        >>> results = list(batch_process(tickers, batch_size=50, processor=process_batch))
    """
    total = len(items)
    processed = 0
    
    for i in range(0, total, batch_size):
        batch = items[i:i + batch_size]
        
        try:
            if processor:
                results = processor(batch)
                for result in results:
                    yield result
            else:
                for item in batch:
                    yield item
            
            processed += len(batch)
            
            # 每处理完一批，强制垃圾回收
            if enable_gc and i % (batch_size * 5) == 0:
                gc.collect()
                
        except Exception as e:
            logger.error(f"Error processing batch {i//batch_size}: {e}")
            raise
    
    logger.info(f"Batch processing complete: {processed}/{total} items")


def chunked_iterator(
    iterator: Iterator[T],
    chunk_size: int = 100,
) -> Iterator[List[T]]:
    """将迭代器分块.
    
    Args:
        iterator: 输入迭代器
        chunk_size: 每块大小
        
    Yields:
        数据块列表
    """
    chunk = []
    for item in iterator:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    
    if chunk:
        yield chunk


def stream_process(
    source: Iterator[T],
    processor: Callable[[T], Optional[T]],
    error_handler: Callable[[T, Exception], None] = None,
) -> Iterator[T]:
    """流式处理数据.
    
    Args:
        source: 数据源迭代器
        processor: 处理函数
        error_handler: 错误处理函数
        
    Yields:
        处理后的数据项
    """
    processed = 0
    errors = 0
    
    for item in source:
        try:
            result = processor(item)
            if result is not None:
                yield result
            processed += 1
            
            # 定期垃圾回收
            if processed % 1000 == 0:
                gc.collect()
                
        except Exception as e:
            errors += 1
            if error_handler:
                error_handler(item, e)
            else:
                logger.warning(f"Error processing item {processed}: {e}")
    
    logger.info(f"Stream processing complete: {processed} processed, {errors} errors")


def parallel_batch_process(
    items: List[T],
    batch_size: int = 100,
    max_workers: int = 4,
) -> Iterator[T]:
    """并行批量处理（预留接口）.
    
    Args:
        items: 待处理的数据列表
        batch_size: 每批大小
        max_workers: 最大工作线程数
        
    Yields:
        处理后的数据项
    """
    # 当前版本使用单线程，预留多线程接口
    #  future: 使用 concurrent.futures.ThreadPoolExecutor
    yield from batch_process(items, batch_size)


def memory_efficient_scan(
    tickers: List[str],
    scanner_func: Callable[[str], T],
    batch_size: int = 50,
) -> Iterator[T]:
    """内存高效的扫描器.
    
    用于 DailyScanner 等批量扫描场景，避免一次性加载所有结果到内存。
    
    Args:
        tickers: 股票代码列表
        scanner_func: 单个股票的扫描函数
        batch_size: 批次大小
        
    Yields:
        扫描结果
        
    Example:
        >>> for report in memory_efficient_scan(tickers, aggregator.generate_report):
        ...     process_report(report)
    """
    total = len(tickers)
    processed = 0
    errors = 0
    
    for i in range(0, total, batch_size):
        batch = tickers[i:i + batch_size]
        
        for ticker in batch:
            try:
                result = scanner_func(ticker)
                yield result
                processed += 1
            except Exception as e:
                logger.error(f"Error scanning {ticker}: {e}")
                errors += 1
        
        # 每批处理后垃圾回收
        gc.collect()
        logger.debug(f"Progress: {processed}/{total}, batch {i//batch_size + 1}")
    
    logger.info(f"Scan complete: {processed} success, {errors} errors")


def optimize_dataframe_chunks(df_iterator: Iterator, chunk_size: int = 10000):
    """优化 DataFrame 分块处理.
    
    Args:
        df_iterator: DataFrame 迭代器
        chunk_size: 每块行数
        
    Yields:
        处理后的 DataFrame chunk
    """
    chunk_num = 0
    
    for chunk in df_iterator:
        chunk_num += 1
        
        # 优化数据类型
        for col in chunk.select_dtypes(include=['float64']).columns:
            chunk[col] = chunk[col].astype('float32')
        
        for col in chunk.select_dtypes(include=['int64']).columns:
            chunk[col] = chunk[col].astype('int32')
        
        yield chunk
        
        # 定期清理
        if chunk_num % 10 == 0:
            gc.collect()


class BatchProgressTracker:
    """批量处理进度追踪器."""
    
    def __init__(self, total: int, batch_size: int = 100):
        self.total = total
        self.batch_size = batch_size
        self.processed = 0
        self.errors = 0
        self.current_batch = 0
        self.total_batches = (total + batch_size - 1) // batch_size
    
    def update(self, batch_count: int, error_count: int = 0):
        """更新进度."""
        self.processed += batch_count
        self.errors += error_count
        self.current_batch += 1
        
        progress = (self.processed / self.total) * 100
        logger.info(
            f"Progress: {progress:.1f}% ({self.processed}/{self.total}), "
            f"Batch {self.current_batch}/{self.total_batches}, "
            f"Errors: {self.errors}"
        )
    
    @property
    def is_complete(self) -> bool:
        """是否完成."""
        return self.processed >= self.total
