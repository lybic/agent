"""Base mixin for Lybic backend sandbox destruction functionality."""

import asyncio
import logging

log = logging.getLogger(__name__)


class LybicSandboxDestroyMixin:
    """
    Mixin class providing sandbox destruction functionality for Lybic-based backends.
    
    This mixin requires the following attributes to be present in the class:
    - sandbox_id: str - The ID of the current sandbox
    - precreate_sid: str - The pre-created sandbox ID (if any)
    - sandbox_manager: Sandbox - The Lybic SDK Sandbox manager instance
    - loop: asyncio.EventLoop - The asyncio event loop
    """
    
    def destroy_sandbox(self):
        """
        Destroy the current sandbox using the Lybic SDK.
        
        This method destroys the sandbox associated with this backend instance.
        Pre-created sandboxes (those provided via precreate_sid) are NOT destroyed
        to prevent accidental deletion of shared or persistent sandboxes.
        
        The method handles both running and non-running event loops properly
        and includes comprehensive error handling with logging.
        
        Raises:
            RuntimeError: If there are issues executing the async delete operation
            Exception: Any exceptions from the Lybic SDK delete API are caught and logged
        
        Note:
            - Only sandboxes created by this instance are destroyed
            - Pre-created sandboxes are skipped with an informational log
            - Errors during destruction are logged but not re-raised
        """
        if not self.sandbox_id:
            log.warning("No sandbox ID available to destroy")
            return
        
        if not self.precreate_sid:
            # Only destroy sandboxes that were created by this instance
            # Don't destroy pre-created sandboxes
            log.info(f"Destroying sandbox: {self.sandbox_id}")
            
            async def _delete_sandbox():
                await self.sandbox_manager.delete(self.sandbox_id)
            
            try:
                if self.loop.is_running():
                    # Schedule delete on the loop
                    future = asyncio.run_coroutine_threadsafe(_delete_sandbox(), self.loop)
                    future.result(timeout=10.0)
                else:
                    # Safe to run directly if loop is not running
                    try:
                        self.loop.run_until_complete(_delete_sandbox())
                    except RuntimeError:
                        # If we can't use the existing loop, create a new one
                        asyncio.run(_delete_sandbox())
                log.info(f"Successfully destroyed sandbox: {self.sandbox_id}")
            except Exception as e:
                log.error(f"Failed to destroy sandbox {self.sandbox_id}: {e}")
        else:
            log.info(f"Skipping destruction of pre-created sandbox: {self.sandbox_id}")
