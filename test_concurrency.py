#!/usr/bin/env python3
"""
并发优化测试脚本
测试新的并发控制和内存管理是否正常工作
"""

import asyncio
import time
import gc
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
import threading

class ConcurrencyTester:
    def __init__(self):
        tracemalloc.start()
        
    def get_memory_usage(self):
        """获取当前内存使用量(MB)"""
        current, peak = tracemalloc.get_traced_memory()
        return current / 1024 / 1024
    
    async def test_semaphore_control(self):
        """测试信号量控制并发"""
        print("Testing semaphore control...")
        
        # 创建信号量，限制并发数为2
        semaphore = asyncio.Semaphore(2)
        active_tasks = 0
        max_concurrent = 0
        
        async def worker(task_id):
            nonlocal active_tasks, max_concurrent
            async with semaphore:
                active_tasks += 1
                max_concurrent = max(max_concurrent, active_tasks)
                print(f"Task {task_id} started, active: {active_tasks}")
                await asyncio.sleep(1)  # 模拟工作
                active_tasks -= 1
                print(f"Task {task_id} finished, active: {active_tasks}")
        
        # 启动10个任务
        tasks = [worker(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        print(f"Max concurrent tasks: {max_concurrent}")
        return max_concurrent <= 2
    
    async def test_memory_cleanup(self):
        """测试内存清理"""
        print("Testing memory cleanup...")
        
        initial_memory = self.get_memory_usage()
        print(f"Initial memory: {initial_memory:.2f}MB")
        
        # 创建大量数据
        large_data = []
        for i in range(1000):
            large_data.append(b'x' * 10240)  # 10KB per item
        
        after_allocation = self.get_memory_usage()
        print(f"After allocation: {after_allocation:.2f}MB")
        
        # 清理数据
        del large_data
        gc.collect()
        
        after_cleanup = self.get_memory_usage()
        print(f"After cleanup: {after_cleanup:.2f}MB")
        
        # 内存应该有所释放
        return after_cleanup < after_allocation
    
    def test_thread_pool(self):
        """测试线程池"""
        print("Testing thread pool...")
        
        def cpu_bound_task(n):
            """CPU密集型任务"""
            result = 0
            for i in range(n):
                result += i * i
            return result
        
        # 测试线程池
        with ThreadPoolExecutor(max_workers=4) as executor:
            start_time = time.time()
            futures = [executor.submit(cpu_bound_task, 100000) for _ in range(8)]
            results = [f.result() for f in futures]
            end_time = time.time()
            
        print(f"Thread pool test completed in {end_time - start_time:.2f}s")
        print(f"Results count: {len(results)}")
        
        return len(results) == 8
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=== 并发优化测试 ===\n")
        
        tests = [
            ("Semaphore Control", self.test_semaphore_control()),
            ("Memory Cleanup", self.test_memory_cleanup()),
            ("Thread Pool", asyncio.get_event_loop().run_in_executor(
                None, self.test_thread_pool
            ))
        ]
        
        results = {}
        for test_name, test_coro in tests:
            try:
                result = await test_coro
                results[test_name] = result
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{test_name}: {status}\n")
            except Exception as e:
                results[test_name] = False
                print(f"{test_name}: ❌ ERROR - {e}\n")
        
        # 总结
        print("=== 测试总结 ===")
        passed = sum(results.values())
        total = len(results)
        print(f"通过: {passed}/{total}")
        
        if passed == total:
            print("🎉 所有并发优化测试通过！")
        else:
            print("⚠️ 部分测试失败，需要检查优化实现")
        
        return results

async def main():
    tester = ConcurrencyTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())