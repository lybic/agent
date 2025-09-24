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
    Click,
    DoubleClick,
    Move,
    Drag,
    TypeText,
    Scroll,
    Hotkey,
    Wait,
    Screenshot,
    Memorize
)

from gui_agents.agents.Backend.Backend import Backend

# 导入官方Lybic SDK
try:
    from lybic import LybicClient, Sandbox, ComputerUse, dto
except ImportError:
    raise ImportError(
        "Lybic Python SDK not found. Please install it with: pip install --upgrade lybic"
    )


log = logging.getLogger(__name__)


class LybicBackend(Backend):
    """
    基于官方Lybic Python SDK的Backend实现
    支持与原LybicBackend相同的Action类型，但使用官方SDK替代HTTP调用
    """
    
    _supported = {Click, DoubleClick, Move, Drag, TypeText, Scroll, Hotkey,
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
        初始化LybicBackend
        
        Args:
            api_key: Lybic API密钥，如果为None则从环境变量LYBIC_API_KEY获取
            org_id: Lybic组织ID，如果为None则从环境变量LYBIC_ORG_ID获取
            endpoint: API端点，如果为None则从环境变量LYBIC_API_ENDPOINT获取
            timeout: API请求超时时间
            extra_headers: 额外的HTTP头
            sandbox_opts: 创建沙盒时的额外选项
            max_retries: 最大重试次数
            precreate_sid: 预创建的沙盒ID，如果提供则不会创建新沙盒
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
                org_id=self.org_id,
                api_key=self.api_key,
                endpoint=self.endpoint,
                timeout=self.timeout,
                extra_headers=self.extra_headers or {}
            )
        else:
            raise ValueError("LYBIC_API_KEY and LYBIC_ORG_ID are required. Please set them as environment variables or pass them as arguments.")
        
        # 初始化SDK组件
        self.sandbox_manager = Sandbox(self.client)
        self.computer_use = ComputerUse(self.client)
        
        # 沙盒ID
        self.sandbox_id = self.precreate_sid
        
        # 如果没有预创建的沙盒ID，则创建新沙盒
        if self.sandbox_id is None:
            print("Creating sandbox using official SDK...")
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
            print(f"Created sandbox: {self.sandbox_id}")

    def __del__(self):
        """清理资源"""
        try:
            if hasattr(self, 'client'):
                self.loop.run_until_complete(self.client.close())
        except Exception as e:
            log.warning(f"Error closing Lybic client: {e}")

    def execute(self, action: Action) -> Any:
        """
        执行Action，将其转换为Lybic SDK调用
        """
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} unsupported")
        if not self.sandbox_id:
            raise RuntimeError("Sandbox ID is empty; create a sandbox first (precreate_sid or auto-create).")

        if isinstance(action, Click):
            return self._click(action)
        elif isinstance(action, DoubleClick):
            return self._double_click(action)
        elif isinstance(action, Move):
            return self._move(action)
        elif isinstance(action, Drag):
            return self._drag(action)
        elif isinstance(action, TypeText):
            return self._type(action)
        elif isinstance(action, Scroll):
            return self._scroll(action)
        elif isinstance(action, Hotkey):
            return self._hotkey(action)
        elif isinstance(action, Screenshot):
            return self._screenshot()
        elif isinstance(action, Wait):
            duration = action.duration if action.duration is not None else 0.2
            time.sleep(duration)
        elif isinstance(action, Memorize):
            log.info(f"Memorizing information: {action.information}")

    def _execute_with_retry(self, action_dto: dto.ComputerUseActionDto) -> dto.SandboxActionResponseDto:
        """
        带重试机制的执行方法
        """
        async def _execute():
            return await self.computer_use.execute_computer_use_action(
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

    def _click(self, act: Click) -> dto.SandboxActionResponseDto:
        """执行点击操作"""
        click_action = dto.MouseClickAction(
            type="mouse:click",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            button=1 if act.button == 0 else 2,  # 0=左键, 1=右键 -> 1=左键, 2=右键
            holdKey=" ".join(act.holdKey) if act.holdKey else ""
        )
        
        action_dto = dto.ComputerUseActionDto(
            action=click_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _double_click(self, act: DoubleClick) -> dto.SandboxActionResponseDto:
        """执行双击操作"""
        double_click_action = dto.MouseDoubleClickAction(
            type="mouse:doubleClick",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            button=1 if act.button == 0 else 2,
            holdKey=" ".join(act.holdKey) if act.holdKey else ""
        )
        
        action_dto = dto.ComputerUseActionDto(
            action=double_click_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _move(self, act: Move) -> dto.SandboxActionResponseDto:
        """执行鼠标移动操作"""
        move_action = dto.MouseMoveAction(
            type="mouse:move",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            holdKey=" ".join(act.holdKey) if act.holdKey else ""
        )
        
        action_dto = dto.ComputerUseActionDto(
            action=move_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _drag(self, act: Drag) -> dto.SandboxActionResponseDto:
        """执行拖拽操作"""
        drag_action = dto.MouseDragAction(
            type="mouse:drag",
            startX=dto.PixelLength(type="px", value=act.startX),
            startY=dto.PixelLength(type="px", value=act.startY),
            endX=dto.PixelLength(type="px", value=act.endX),
            endY=dto.PixelLength(type="px", value=act.endY),
            holdKey=" ".join(act.holdKey) if act.holdKey else ""
        )
        
        action_dto = dto.ComputerUseActionDto(
            action=drag_action,
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
        
        action_dto = dto.ComputerUseActionDto(
            action=type_action,
            includeScreenShot=False,
            includeCursorPosition=False
        )
        
        return self._execute_with_retry(action_dto)

    def _scroll(self, act: Scroll) -> dto.SandboxActionResponseDto:
        """执行滚动操作"""
        # 根据滚动方向确定stepVertical和stepHorizontal
        step_vertical = 0
        step_horizontal = 0
        
        if act.stepVertical is not None:
            step_vertical = act.stepVertical
        if act.stepHorizontal is not None:
            step_horizontal = act.stepHorizontal
            
        scroll_action = dto.MouseScrollAction(
            type="mouse:scroll",
            x=dto.PixelLength(type="px", value=act.x),
            y=dto.PixelLength(type="px", value=act.y),
            stepVertical=step_vertical,
            stepHorizontal=step_horizontal,
            holdKey=" ".join(act.holdKey) if act.holdKey else ""
        )
        
        action_dto = dto.ComputerUseActionDto(
            action=scroll_action,
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
        
        action_dto = dto.ComputerUseActionDto(
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
        if self.sandbox_id is None:
            raise RuntimeError("Sandbox ID is not available")
        return self.sandbox_id

    def close(self):
        """关闭客户端连接"""
        try:
            self.loop.run_until_complete(self.client.close())
        except Exception as e:
            log.warning(f"Error closing Lybic client: {e}")
