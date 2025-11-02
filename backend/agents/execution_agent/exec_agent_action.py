"""
Action Layer Module
Executes physical interactions: click, type, scroll, etc.

Author: Accessibility AI Team
Version: 1.0.0
"""

import time
from typing import Tuple

from exec_agent_config import Config
from exec_agent_deps import PYAUTOGUI_AVAILABLE, pyautogui


class ActionLayer:
    """
    Executes physical interactions: click, type, scroll, etc.
    """
    
    def __init__(self, logger, vision_layer):
        self.logger = logger
        self.vision = vision_layer
    
    def click(self, coordinates: Tuple[int, int], button='left') -> bool:
        """
        Click at specific coordinates
        
        Args:
            coordinates: (x, y) tuple
            button: Mouse button ('left', 'right', 'middle')
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            self.logger.error("PyAutoGUI not available for clicking")
            return False
        
        try:
            x, y = coordinates
            pyautogui.click(x, y, button=button)
            self.logger.info(f"Clicked at ({x}, {y}) with {button} button")
            time.sleep(Config.CLICK_DELAY)
            return True
        except Exception as e:
            self.logger.error(f"Click failed: {e}")
            return False
    
    def double_click(self, coordinates: Tuple[int, int]) -> bool:
        """
        Double-click at specific coordinates
        
        Args:
            coordinates: (x, y) tuple
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            self.logger.error("PyAutoGUI not available")
            return False
        
        try:
            x, y = coordinates
            pyautogui.doubleClick(x, y)
            self.logger.info(f"Double-clicked at ({x}, {y})")
            time.sleep(Config.CLICK_DELAY)
            return True
        except Exception as e:
            self.logger.error(f"Double-click failed: {e}")
            return False
    
    def type_text(self, text: str, interval=None) -> bool:
        """
        Type text with specified interval
        
        Args:
            text: Text to type
            interval: Interval between keystrokes (default from Config)
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            self.logger.error("PyAutoGUI not available for typing")
            return False
        
        if interval is None:
            interval = Config.TYPE_INTERVAL
        
        try:
            pyautogui.write(text, interval=interval)
            self.logger.info(f"Typed text: {text[:50]}...")
            return True
        except Exception as e:
            self.logger.error(f"Typing failed: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """
        Press a keyboard key
        
        Args:
            key: Key name (e.g., 'enter', 'tab', 'esc')
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.press(key)
            self.logger.info(f"Pressed key: {key}")
            time.sleep(Config.KEY_PRESS_DELAY)
            return True
        except Exception as e:
            self.logger.error(f"Key press failed: {e}")
            return False
    
    def hotkey(self, *keys) -> bool:
        """
        Press keyboard shortcut
        
        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.hotkey(*keys)
            self.logger.info(f"Pressed hotkey: {'+'.join(keys)}")
            time.sleep(Config.CLICK_DELAY)
            return True
        except Exception as e:
            self.logger.error(f"Hotkey failed: {e}")
            return False
    
    def scroll(self, clicks: int) -> bool:
        """
        Scroll mouse wheel
        
        Args:
            clicks: Number of clicks (positive=up, negative=down)
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.scroll(clicks)
            direction = "up" if clicks > 0 else "down"
            self.logger.info(f"Scrolled {abs(clicks)} clicks {direction}")
            time.sleep(0.3)
            return True
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
            return False
    
    def move_to(self, coordinates: Tuple[int, int], duration=0.5) -> bool:
        """
        Move mouse to coordinates
        
        Args:
            coordinates: (x, y) tuple
            duration: Movement duration in seconds
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            x, y = coordinates
            pyautogui.moveTo(x, y, duration=duration)
            self.logger.info(f"Moved mouse to ({x}, {y})")
            return True
        except Exception as e:
            self.logger.error(f"Mouse move failed: {e}")
            return False
    
    def drag_to(self, coordinates: Tuple[int, int], duration=0.5) -> bool:
        """
        Drag mouse to coordinates
        
        Args:
            coordinates: (x, y) tuple
            duration: Movement duration in seconds
        
        Returns:
            Success status
        """
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            x, y = coordinates
            pyautogui.dragTo(x, y, duration=duration)
            self.logger.info(f"Dragged mouse to ({x}, {y})")
            return True
        except Exception as e:
            self.logger.error(f"Drag failed: {e}")
            return False
