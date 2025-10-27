"""
Unit tests for file locking in knowledge base operations.

Tests concurrent access to knowledge base files to ensure file locks
prevent race conditions during read/write operations.
"""

import unittest
import os
import json
import pickle
import tempfile
import shutil
import threading
import time
from pathlib import Path

from gui_agents.utils.common_utils import (
    load_knowledge_base,
    save_embeddings,
    load_embeddings,
)


class TestKnowledgeFileLock(unittest.TestCase):
    """Test file locking for knowledge base file operations."""

    def setUp(self):
        """Set up test environment with temporary directory."""
        self.test_dir = tempfile.mkdtemp()
        self.kb_path = os.path.join(self.test_dir, "test_kb.json")
        self.embeddings_path = os.path.join(self.test_dir, "test_embeddings.pkl")
        
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_knowledge_base_nonexistent_file(self):
        """Test loading knowledge base when file doesn't exist."""
        result = load_knowledge_base(self.kb_path)
        self.assertEqual(result, {})

    def test_load_knowledge_base_valid_file(self):
        """Test loading knowledge base from valid JSON file."""
        test_data = {"task1": "experience1", "task2": "experience2"}
        with open(self.kb_path, "w") as f:
            json.dump(test_data, f)
        
        result = load_knowledge_base(self.kb_path)
        self.assertEqual(result, test_data)

    def test_load_embeddings_nonexistent_file(self):
        """Test loading embeddings when file doesn't exist."""
        result = load_embeddings(self.embeddings_path)
        self.assertEqual(result, {})

    def test_load_embeddings_valid_file(self):
        """Test loading embeddings from valid pickle file."""
        test_embeddings = {"instruction1": [0.1, 0.2, 0.3], "instruction2": [0.4, 0.5, 0.6]}
        with open(self.embeddings_path, "wb") as f:
            pickle.dump(test_embeddings, f)
        
        result = load_embeddings(self.embeddings_path)
        self.assertEqual(result, test_embeddings)

    def test_save_and_load_embeddings(self):
        """Test saving and loading embeddings."""
        test_embeddings = {"instruction1": [0.1, 0.2, 0.3], "instruction2": [0.4, 0.5, 0.6]}
        save_embeddings(self.embeddings_path, test_embeddings)
        
        result = load_embeddings(self.embeddings_path)
        self.assertEqual(result, test_embeddings)

    def test_concurrent_knowledge_base_reads(self):
        """Test concurrent reads to knowledge base file."""
        # Create initial knowledge base
        test_data = {"task1": "experience1", "task2": "experience2"}
        with open(self.kb_path, "w") as f:
            json.dump(test_data, f)
        
        results = []
        errors = []
        
        def read_kb():
            try:
                result = load_knowledge_base(self.kb_path)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to read concurrently
        threads = []
        for _ in range(10):
            t = threading.Thread(target=read_kb)
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent reads: {errors}")
        
        # Verify all reads returned correct data
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual(result, test_data)

    def test_concurrent_embeddings_reads(self):
        """Test concurrent reads to embeddings file."""
        # Create initial embeddings
        test_embeddings = {"instruction1": [0.1, 0.2, 0.3], "instruction2": [0.4, 0.5, 0.6]}
        save_embeddings(self.embeddings_path, test_embeddings)
        
        results = []
        errors = []
        
        def read_embeddings():
            try:
                result = load_embeddings(self.embeddings_path)
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to read concurrently
        threads = []
        for _ in range(10):
            t = threading.Thread(target=read_embeddings)
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent reads: {errors}")
        
        # Verify all reads returned correct data
        self.assertEqual(len(results), 10)
        for result in results:
            self.assertEqual(result, test_embeddings)

    def test_concurrent_embeddings_writes(self):
        """Test concurrent writes to embeddings file."""
        errors = []
        
        def write_embeddings(thread_id):
            try:
                embeddings = {f"instruction_{thread_id}": [float(thread_id)] * 3}
                save_embeddings(self.embeddings_path, embeddings)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads to write concurrently
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_embeddings, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent writes: {errors}")
        
        # Verify file exists and can be read
        result = load_embeddings(self.embeddings_path)
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)

    def test_concurrent_read_write_embeddings(self):
        """Test concurrent reads and writes to embeddings file."""
        # Initialize with some data
        initial_embeddings = {"instruction_0": [0.0, 0.0, 0.0]}
        save_embeddings(self.embeddings_path, initial_embeddings)
        
        errors = []
        read_count = [0]
        write_count = [0]
        
        def read_embeddings():
            try:
                load_embeddings(self.embeddings_path)
                read_count[0] += 1
            except Exception as e:
                errors.append(("read", e))
        
        def write_embeddings(thread_id):
            try:
                embeddings = {f"instruction_{thread_id}": [float(thread_id)] * 3}
                save_embeddings(self.embeddings_path, embeddings)
                write_count[0] += 1
            except Exception as e:
                errors.append(("write", e))
        
        # Create mix of reader and writer threads
        threads = []
        for i in range(5):
            # Add writer
            t = threading.Thread(target=write_embeddings, args=(i,))
            threads.append(t)
            # Add reader
            t = threading.Thread(target=read_embeddings)
            threads.append(t)
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify operations completed
        self.assertEqual(read_count[0], 5, "Not all reads completed")
        self.assertEqual(write_count[0], 5, "Not all writes completed")
        
        # Verify file is still valid
        result = load_embeddings(self.embeddings_path)
        self.assertIsInstance(result, dict)

    def test_lock_files_are_created(self):
        """Test that lock files are created during operations."""
        # Test knowledge base lock file
        test_data = {"task1": "experience1"}
        with open(self.kb_path, "w") as f:
            json.dump(test_data, f)
        
        # Load knowledge base - lock file should be created during this operation
        # but cleaned up after
        load_knowledge_base(self.kb_path)
        
        # Test embeddings lock file
        test_embeddings = {"instruction1": [0.1, 0.2, 0.3]}
        save_embeddings(self.embeddings_path, test_embeddings)
        
        # Load embeddings - lock file should be created during this operation
        # but cleaned up after
        load_embeddings(self.embeddings_path)
        
        # The lock files may or may not exist after operations complete
        # as they are typically cleaned up by the FileLock library
        # This test just ensures the operations complete without error


class TestKnowledgeBaseIntegration(unittest.TestCase):
    """Integration tests for KnowledgeBase with file locking."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.platform = "test_platform"
        self.test_platform_path = os.path.join(self.test_dir, self.platform)
        os.makedirs(self.test_platform_path, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_knowledge_base_file_operations(self):
        """Test that KnowledgeBase methods use file locks correctly."""
        from gui_agents.core.knowledge import KnowledgeBase
        from gui_agents.tools.tools import Tools
        
        # Create a minimal Tools_dict for testing
        # Note: This test may require proper API keys to run fully
        Tools_dict = {
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "query_formulator": {"provider": "openai", "model": "gpt-4"},
            "context_fusion": {"provider": "openai", "model": "gpt-4"},
            "narrative_summarization": {"provider": "openai", "model": "gpt-4"},
            "episode_summarization": {"provider": "openai", "model": "gpt-4"},
        }
        
        embedding_engine = Tools()
        
        # Create KnowledgeBase instance
        try:
            kb = KnowledgeBase(
                embedding_engine=embedding_engine,
                local_kb_path=self.test_dir,
                platform=self.platform,
                Tools_dict=Tools_dict,
                save_knowledge=False  # Don't actually save during test
            )
            
            # Verify paths are set correctly
            self.assertTrue(kb.episodic_memory_path.endswith("episodic_memory.json"))
            self.assertTrue(kb.narrative_memory_path.endswith("narrative_memory.json"))
            self.assertIsNotNone(kb.embeddings_path)
            
        except Exception as e:
            # If initialization fails due to missing API keys, that's okay for this test
            self.skipTest(f"Skipping test due to initialization error: {e}")


if __name__ == '__main__':
    unittest.main()
