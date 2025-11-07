# ---------------------------------------------------------------------------
# 3) Cloud desktop / custom device backend using Official Lybic Python SDK
# https://lybic.ai/docs/sdk/python
# ---------------------------------------------------------------------------
import asyncio
import logging
import time
import os
from typing import Dict, Any, Optional
from PIL import Image

from gui_agents.agents.Action import (
    Action,
    TouchTap,
    TouchDrag,
    TouchSwipe,
    TouchLongPress,
    AndroidHome,
    AndroidBack,
    TypeText,
    Hotkey,
    Wait,
    Screenshot,
    Memorize
)

from gui_agents.agents.Backend.Backend import Backend
from gui_agents.agents.Backend.LybicBackendBase import LybicSandboxDestroyMixin

# 导入官方Lybic SDK
try:
    from lybic import LybicClient, Sandbox, dto, LybicAuth
except ImportError:
    raise ImportError(
        "Lybic Python SDK not found. Please install it with: pip install --upgrade lybic"
    )


log = logging.getLogger(__name__)


class LybicMobileBackend(LybicSandboxDestroyMixin, Backend):
    
    _supported = {TouchTap, TouchDrag, TouchSwipe, TouchLongPress, AndroidHome, AndroidBack, TypeText, Hotkey,
                  Wait, Screenshot, Memorize}

    def __init__(self, 
                 api_key: Optional[str] = None,
                 org_id: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 timeout: int = 10,
                 extra_headers: Optional[Dict[str, str]] = None,
                 sandbox_opts: Optional[Dict[str, Any]] = None,
                 max_retries: int = 2,
                 precreate_sid: str = '',
                 **kwargs):
        """
                 Initialize the LybicBackend, create and configure the Lybic SDK client, and ensure a sandbox is available.
                 
                 Parameters:
                     api_key (Optional[str]): Lybic API key; if None the value is read from the LYBIC_API_KEY environment variable.
                     org_id (Optional[str]): Lybic organization ID; if None the value is read from the LYBIC_ORG_ID environment variable.
                     endpoint (Optional[str]): API endpoint; if None the value is read from LYBIC_API_ENDPOINT (default "https://api.lybic.cn").
                     timeout (int): Request timeout in seconds for the SDK client.
                     extra_headers (Optional[Dict[str, str]]): Additional HTTP headers to pass to the SDK via LybicAuth.
                     sandbox_opts (Optional[Dict[str, Any]]): Options used when creating a new sandbox; LYBIC_MAX_LIFE_SECONDS is applied as the default for `maxLifeSeconds` if not provided.
                     max_retries (int): Maximum number of retry attempts for action execution.
                     precreate_sid (str): Pre-created sandbox ID to use; if empty, a new sandbox will be created.
                 
                 Raises:
                     ValueError: If neither api_key nor org_id are provided (and not present in the corresponding environment variables).
                     RuntimeError: If sandbox creation completes but no sandbox ID can be obtained from the SDK response.
                 """
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 初始化参数
        self.api_key = api_key or os.getenv("LYBIC_API_KEY")
        self.org_id = org_id or os.getenv("LYBIC_ORG_ID")
        self.endpoint = endpoint or os.getenv("LYBIC_API_ENDPOINT", "https://api.lybic.cn")
        self.timeout = timeout
        self.extra_headers = extra_headers
        self.max_retries = max_retries
        self.precreate_sid = precreate_sid or os.getenv("LYBIC_PRECREATE_SID", "")
        
        # 初始化SDK客户端（仅在有必要参数时）
        if self.api_key and self.org_id:
            self.client = LybicClient(
                LybicAuth(
                    org_id=self.org_id,
                    api_key=self.api_key,
                    endpoint=self.endpoint,
                    extra_headers=self.extra_headers or {}
                ),
                timeout=self.timeout,
            )
        else:
            raise ValueError("LYBIC_API_KEY and LYBIC_ORG_ID are required. Please set them as environment variables or pass them as arguments.")
        
        # 初始化SDK组件
        self.sandbox_manager = Sandbox(self.client)
        
        # 沙盒ID
        self.sandbox_id = self.precreate_sid
        
        # 如果没有预创建的沙盒ID，则创建新沙盒
        if not self.sandbox_id:
            log.info("Creating sandbox using official SDK...")
            max_life_seconds = int(os.getenv("LYBIC_MAX_LIFE_SECONDS", "3600"))
            sandbox_opts = sandbox_opts or {}
            sandbox_opts.setdefault("maxLifeSeconds", max_life_seconds)
            
            new_sandbox = self.loop.run_until_complete(
                self.sandbox_manager.create(
                    name=sandbox_opts.get("name", "agent-run"),
                    **sandbox_opts
                )
            )
            # 使用getattr以防属性名不同
            self.sandbox_id = getattr(new_sandbox, 'id', "") or getattr(new_sandbox, 'sandbox_id', "")
            if not self.sandbox_id:
                raise RuntimeError(f"Failed to get sandbox ID from response: {new_sandbox}")
            log.info(f"Created sandbox: {self.sandbox_id}")

    def __del__(self):
        """清理资源"""
        try:
            if hasattr(self, 'client'):
                self.loop.run_until_complete(self.client.close())
        except Exception as e:
            log.warning(f"Error closing Lybic client: {e}")

    def execute(self, action: Action) -> Any:
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} unsupported")
        if not self.sandbox_id:
            raise RuntimeError("Sandbox ID is empty; create a sandbox first (precreate_sid or auto-create).")

        if isinstance(action, TouchTap):
            return self._touchtap(action)
        elif isinstance(action, TouchDrag):
            return self._touchdrag(action)
        elif isinstance(action, TouchSwipe):
            return self._touchswipe(action)
        elif isinstance(action, TouchLongPress):
            return self._touchlongpress(action)
        elif isinstance(action, AndroidHome):
            return self._android_home(action)
        elif isinstance(action, AndroidBack):
            return self._android_back(action)
        elif isinstance(action, TypeText):
            return self._type(action)
        elif isinstance(action, Hotkey):
            return self._hotkey(action)
        elif isinstance(action, Screenshot):
            return self._screenshot()
        elif isinstance(action, Wait):
            duration = action.duration if action.duration is not None else 0.2
            time.sleep(duration)
        elif isinstance(action, Memorize):
            log.info(f"Memorizing information: {action.information}")

    def _execute_with_retry(self, action_dto: dto.ExecuteSandboxActionDto) -> dto.SandboxActionResponseDto:
        """
        带重试机制的执行方法
        """
        async def _execute():
            return await self.sandbox_manager.execute_sandbox_action(
                sandbox_id=self.sandbox_id,
                data=action_dto
            )

        exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 2):
            try:
                return self.loop.run_until_complete(_execute())
            except Exception as e:
                exc = e
                log.warning(f"Lybic SDK action failed (try {attempt}/{self.max_retries+1}): {e}")
                time.sleep(0.4 * attempt)  # 退避策略
        
        raise RuntimeError(f"Lybic SDK action failed after {self.max_retries + 1} attempts: {exc}") from exc

    def _touchtap(self, act: TouchTap) -> dto.SandboxActionResponseDto:
        """执行点击操作"""
        tap_action = dto.TouchTapAction(
            type="touch:tap",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=tap_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _touchdrag(self, act: TouchDrag) -> dto.SandboxActionResponseDto:
        """执行拖拽操作"""
        drag_action = dto.TouchDragAction(
            type="touch:drag",
            startX=dto.PixelLength(type="px", value=act.startX),
            startY=dto.PixelLength(type="px", value=act.startY),
            endX=dto.PixelLength(type="px", value=act.endX),
            endY=dto.PixelLength(type="px", value=act.endY),
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=drag_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _touchswipe(self, act: TouchSwipe) -> dto.SandboxActionResponseDto:
        """执行滑动操作"""
        if act.direction not in ["up", "down", "left", "right"]:
            raise ValueError("Invalid direction for swipe action, must be 'up', 'down', 'left', or 'right'")

        swipe_action = dto.TouchSwipeAction(
            type="touch:swipe",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            direction=act.direction,
            distance=dto.PixelLength(type="px", value=act.distance),
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=swipe_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _touchlongpress(self, act: TouchLongPress) -> dto.SandboxActionResponseDto:
        """执行长按操作"""
        duration = 80  # 默认值
        if act.duration is not None:
            if 1 <= act.duration <= 5000:
                duration = act.duration
            else:
                raise ValueError("longPress duration must be between 1 and 5000")

        longpress_action = dto.TouchLongPressAction(
            type="touch:longPress",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            duration=duration,
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=longpress_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)
    
    def _android_home(self, act: AndroidHome) -> dto.SandboxActionResponseDto:
        """执行返回主屏幕操作"""
        home_action = dto.AndroidHomeAction(
            type="android:home",
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=home_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)
    
    def _android_back(self, act: AndroidBack) -> dto.SandboxActionResponseDto:
        """执行返回操作"""
        back_action = dto.AndroidBackAction(
            type="android:back",
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=back_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _type(self, act: TypeText) -> dto.SandboxActionResponseDto:
        """执行文本输入操作"""
        type_action = dto.KeyboardTypeAction(
            type="keyboard:type",
            content=act.text,
            treatNewLineAsEnter=True  # 默认将换行符作为回车键处理
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=type_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _hotkey(self, act: Hotkey) -> dto.SandboxActionResponseDto:
        """执行快捷键操作"""
        # 处理持续时间
        duration = 80  # 默认值
        if act.duration is not None:
            if 1 <= act.duration <= 5000:
                duration = act.duration
            else:
                raise ValueError("Hotkey duration must be between 1 and 5000")
        
        # 将键列表转换为空格分隔的字符串（根据SDK文档）
        keys_str = " ".join(act.keys).lower()
        
        hotkey_action = dto.KeyboardHotkeyAction(
            type="keyboard:hotkey",
            keys=keys_str,
            duration=duration
        )
        
        action_dto = dto.ExecuteSandboxActionDto(
            action=hotkey_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _screenshot(self) -> Image.Image:
        """
        获取屏幕截图
        使用SDK的get_screenshot方法
        """
        async def _get_screenshot():
            return await self.sandbox_manager.get_screenshot(self.sandbox_id)
        
        try:
            url, image, b64_str = self.loop.run_until_complete(_get_screenshot())
            
            # 返回PIL图像，保持与原LybicBackend的兼容性
            # 如果需要cursor信息，可以通过其他方式获取
            return image
            
        except Exception as e:
            raise RuntimeError(f"Failed to take screenshot: {e}") from e

    def get_sandbox_id(self) -> str:
        """获取当前沙盒ID"""
        if not self.sandbox_id:
            raise RuntimeError("Sandbox ID is not available")
        return self.sandbox_id

    def close(self):
        """关闭客户端连接"""
        try:
            self.loop.run_until_complete(self.client.close())
        except Exception as e:
            log.warning(f"Error closing Lybic client: {e}")
