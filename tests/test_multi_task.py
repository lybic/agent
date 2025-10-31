#!/usr/bin/env python3
"""
测试多任务并行功能，验证Registry的任务隔离是否正常工作
"""

import threading
import time
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from gui_agents.service.agent_service import AgentService
from gui_agents.store.registry import Registry


def test_registry_isolation():
    """测试Registry的任务隔离功能"""
    print("=== 测试Registry任务隔离功能 ===")

    # 清理全局注册表
    Registry.clear()

    results = []

    def worker_task(task_id: str, task_name: str) -> dict:
        """工作线程任务"""
        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix=f"test_task_{task_id}_")

            # 配置AgentService
            service_config = {
                "max_steps": 3,
                "backend": "lybic",
                "local_kb_path": temp_dir,
                "tools_config": {}
            }

            service = AgentService(service_config)

            # 模拟任务执行
            result = {
                "task_id": task_id,
                "task_name": task_name,
                "thread_id": threading.current_thread().ident,
                "temp_dir": temp_dir,
                "status": "started"
            }

            # 尝试获取任务特定的GlobalState
            try:
                global_state = Registry.get_from_context("GlobalStateStore", task_id)
                result["global_state_retrieved"] = True
                result["global_state_id"] = id(global_state)
            except KeyError as e:
                result["global_state_retrieved"] = False
                result["error"] = str(e)

            # 检查任务注册表隔离
            task_registry = Registry.get_task_registry(task_id)
            result["task_registry_exists"] = task_registry is not None

            if task_registry:
                # 在任务注册表中注册一个测试对象
                test_obj = {"test_data": f"task_{task_id}_data"}
                task_registry.register_instance(f"test_obj_{task_id}", test_obj)

                # 验证能够获取到注册的对象
                retrieved_obj = task_registry.get_instance(f"test_obj_{task_id}")
                result["test_obj_registered"] = retrieved_obj == test_obj

            # 模拟一些工作时间
            time.sleep(0.1)

            result["status"] = "completed"
            return result

        except Exception as e:
            return {
                "task_id": task_id,
                "task_name": task_name,
                "status": "failed",
                "error": str(e)
            }

    # 创建多个并发任务
    tasks = [
        ("task_001", "打开记事本"),
        ("task_002", "发送邮件"),
        ("task_003", "浏览网页"),
        ("task_004", "查看文件"),
        ("task_005", "设置提醒")
    ]

    # 使用线程池执行任务
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(worker_task, task_id, task_name): (task_id, task_name)
            for task_id, task_name in tasks
        }

        # 收集结果
        for future in as_completed(future_to_task):
            task_id, task_name = future_to_task[future]
            try:
                result = future.result()
                results.append(result)
                print(f"任务 {task_id} ({task_name}) 完成: {result['status']}")
            except Exception as e:
                print(f"任务 {task_id} ({task_name}) 异常: {e}")
                results.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "status": "exception",
                    "error": str(e)
                })

    # 分析结果
    print("\n=== 测试结果分析 ===")

    successful_tasks = [r for r in results if r.get("status") == "completed"]
    failed_tasks = [r for r in results if r.get("status") in ["failed", "exception"]]

    print(f"总任务数: {len(tasks)}")
    print(f"成功任务数: {len(successful_tasks)}")
    print(f"失败任务数: {len(failed_tasks)}")

    # 检查GlobalState隔离
    global_state_ids = [r.get("global_state_id") for r in successful_tasks if r.get("global_state_retrieved")]
    unique_global_state_ids = set(global_state_ids)

    print(f"GlobalState实例数: {len(unique_global_state_ids)}")
    print(f"预期实例数: {len(successful_tasks)}")

    if len(unique_global_state_ids) == len(successful_tasks):
        print("✅ GlobalState隔离测试通过")
    else:
        print("❌ GlobalState隔离测试失败")

    # 检查任务注册表隔离
    task_registry_exists = [r.get("task_registry_exists") for r in successful_tasks]
    test_obj_registered = [r.get("test_obj_registered") for r in successful_tasks]

    if all(task_registry_exists) and all(test_obj_registered):
        print("✅ 任务注册表隔离测试通过")
    else:
        print("❌ 任务注册表隔离测试失败")

    # 清理临时目录
    for result in results:
        if "temp_dir" in result:
            try:
                shutil.rmtree(result["temp_dir"])
            except Exception:
                pass

    # 清理注册表
    Registry.clear()

    return len(successful_tasks) == len(tasks)


def test_concurrent_registry_access():
    """测试并发Registry访问的线程安全性"""
    print("\n=== 测试Registry并发访问线程安全性 ===")

    # 清理全局注册表
    Registry.clear()

    results = []
    errors = []

    def concurrent_worker(worker_id: int) -> dict:
        """并发工作线程"""
        try:
            # 每个工作者创建自己的任务注册表
            task_id = f"worker_{worker_id}"
            task_registry = Registry()

            # 注册到线程本地存储
            Registry.set_task_registry(task_id, task_registry)

            # 注册一些测试对象
            for i in range(5):
                obj_name = f"obj_{worker_id}_{i}"
                obj_value = f"value_{worker_id}_{i}"
                task_registry.register_instance(obj_name, obj_value)

            # 验证能够正确获取
            retrieved_values = []
            for i in range(5):
                obj_name = f"obj_{worker_id}_{i}"
                try:
                    value = task_registry.get_instance(obj_name)
                    retrieved_values.append(value)
                except KeyError:
                    errors.append(f"Worker {worker_id} failed to retrieve {obj_name}")

            # 模拟一些工作时间
            time.sleep(0.05)

            # 清理
            Registry.remove_task_registry(task_id)

            return {
                "worker_id": worker_id,
                "status": "success",
                "retrieved_count": len(retrieved_values)
            }

        except Exception as e:
            errors.append(f"Worker {worker_id} error: {str(e)}")
            return {
                "worker_id": worker_id,
                "status": "error",
                "error": str(e)
            }

    # 创建多个并发工作者
    num_workers = 10
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(concurrent_worker, i) for i in range(num_workers)]

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append(f"Future error: {str(e)}")

    # 分析结果
    successful_workers = [r for r in results if r.get("status") == "success"]
    failed_workers = [r for r in results if r.get("status") == "error"]

    print(f"总工作者数: {num_workers}")
    print(f"成功工作者数: {len(successful_workers)}")
    print(f"失败工作者数: {len(failed_workers)}")
    print(f"错误数: {len(errors)}")

    if len(failed_workers) == 0 and len(errors) == 0:
        print("✅ Registry并发访问测试通过")
        return True
    else:
        print("❌ Registry并发访问测试失败")
        for error in errors:
            print(f"  错误: {error}")
        return False


def main():
    """主测试函数"""
    print("开始多任务并行功能测试...")

    test_results = []

    # 测试1: Registry隔离功能
    test1_result = test_registry_isolation()
    test_results.append(("Registry隔离功能", test1_result))

    # 测试2: 并发访问线程安全性
    test2_result = test_concurrent_registry_access()
    test_results.append(("并发访问线程安全性", test2_result))

    # 总结测试结果
    print("\n" + "="*50)
    print("测试结果总结:")
    print("="*50)

    all_passed = True
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        all_passed = all_passed and result

    print(f"\n总体结果: {'✅ 所有测试通过' if all_passed else '❌ 存在测试失败'}")

    return all_passed


if __name__ == "__main__":
    main()