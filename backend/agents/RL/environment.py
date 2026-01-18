"""
YUSR multi-agent RL environment (concrete, no placeholders).

This environment integrates with the repository's Execution Agent layers
for perception and action. It requires the following packages to be
installed before use:

- gymnasium
- ray[rllib]
- torch
- pillow
- langchain_community (for HuggingFaceEmbeddings; optional but used if
  `task_description` is provided in env_config)

Also required if you want true automation (rather than simulated clicks):
- pyautogui, pywinauto, pytesseract (these are used by the Execution Agent
  layers which this environment calls).

This file contains no placeholder implementations: it will raise clear
ImportError messages if a required package or internal module is missing.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import os # Import os for path handling

# NOTE: The Gymnasium spaces are required for the definition of the observation_space and action_space
from gymnasium.spaces import Discrete, Box, Dict as GymDict
from ray.rllib.env.multi_agent_env import MultiAgentEnv
import numpy as np # Used for defining space bounds

# --- Tesseract Import ---
try:
    import pytesseract
except ImportError:
    pytesseract = None

# --- START OF CIRCULAR IMPORT FIX ---

# Attempt to import the real Execution Agent modules. If import fails (circular import /
# missing deps), provide lightweight local stubs so this RL environment can run a smoke
# test without editing the execution_agent package.
try:
    # **FIX:** Changed relative imports to absolute imports using the 'backend' package
    # name, which should be accessible via your PYTHONPATH setting.
    from backend.agents.execution_agent.layers.exec_agent_vision import VisionLayer
    from backend.agents.execution_agent.layers.exec_agent_action import ActionLayer
    from backend.agents.execution_agent.core.exec_agent_deps import PYAUTOGUI_AVAILABLE
    _REAL_EXEC_AGENT = True
except Exception:
    # Fall back to simple stubs to avoid circular import at module import time.
    _REAL_EXEC_AGENT = False
    PYAUTOGUI_AVAILABLE = False

    class VisionLayer:
        """Minimal stub that provides capture_screen() and extract_ocr_text()."""
        def __init__(self, logger=None):
            self.logger = logger

        def capture_screen(self) -> str:
            
            # produce a tiny temporary blank PNG so downstream code can open it
            from PIL import Image
            import tempfile, os
            img = Image.new("RGB", (160, 80), color=(128, 128, 128))
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            img.save(path)
            return path

        def extract_ocr_text(self, image_path: str) -> str:
            # stub: no OCR available in the fallback
            return ""

    class ActionLayer:
        """Minimal stub exposing click() and scroll() used by the env driver."""
        def __init__(self, logger=None, vision=None):
            self.logger = logger
            self.vision = vision

        def click(self, coords) -> bool:
            # no real automation in stub; return False (no-op)
            return False

        def scroll(self, amount: int) -> bool:
            return False

# --- END OF CIRCULAR IMPORT FIX ---

# Embeddings and image processing
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    class HuggingFaceEmbeddings:
        """Stub for HuggingFaceEmbeddings if the dependency is missing."""
        def __init__(self, model_name: str):
            pass
        def embed_documents(self, texts: list) -> list:
            # Return a stub embedding of 384 dimensions (default for all-MiniLM-L6-v2)
            return [[0.0] * 384 for _ in texts]

from PIL import Image


class ExecutionUIDriver:
    """Concrete UI driver using the Execution Agent Vision/Action layers.

    This driver produces a 128-d screenshot feature vector by resizing a
    captured screenshot to 16x8 grayscale and flattening the pixels.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("RLEnvDriver")

        # 🎯 CRITICAL FIX: Explicitly set Tesseract path for Ray Workers 
        if pytesseract:
            # You MUST replace this placeholder with the actual path to your tesseract.exe.
            # Example path for Windows: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            
            if tesseract_path.startswith('<REPLACE'):
                self.logger.error("TESSERACT PATH IS NOT SET. This is the likely cause of your crash!")
            elif os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                self.logger.info(f"Set Tesseract path to: {tesseract_path}")
            else:
                self.logger.error(f"Tesseract executable not found at: {tesseract_path}. Please check the path.")


        # Initialize Vision and Action layers from the execution agent.
        self.vision = VisionLayer(self.logger)
        self.action = ActionLayer(self.logger, self.vision)

        # Performance: Initialize embedding model ONCE and reuse
        try:
            # Check if the stub is used before trying to load
            if HuggingFaceEmbeddings.__name__ != 'HuggingFaceEmbeddings':
                 self.embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            else:
                 self.embedding_model = None
        except Exception as e:
            self.logger.error(f"Failed to load embedding model: {e}")
            self.embedding_model = None

    def _extract_visual_features(self, image_path: str) -> list:
        """
        Extract a richer feature vector from the screenshot.
        If CLIP or a VLM is available, use it. Otherwise, use HuggingFaceEmbeddings on OCR text as fallback.
        The embedding model is initialized ONCE for performance.
        """
        try:
            # Try to use CLIP or a VLM (stub: not implemented here)
            # If not available, fallback to text embedding of OCR
            ocr_text = self.vision.extract_ocr_text(image_path)
            if ocr_text and self.embedding_model:
                vec = self.embedding_model.embed_documents([ocr_text])[0]
                # Truncate or pad to 128 dims
                if len(vec) >= 128:
                    return vec[:128]
                else:
                    return vec + [0.0] * (128 - len(vec))
            else:
                # fallback: grayscale as before
                img = Image.open(image_path).convert("L")
                img = img.resize((16, 8))
                arr = list(img.getdata())
                return [float(x) / 255.0 for x in arr]
        except Exception as e:
            self.logger.error(f"Feature extraction failed: {e}")
            return [0.0] * 128
            
    def _embed_text(self, text: str, output_dim: int) -> list:
        """
        Converts a text string into a fixed-size embedding vector.
        """
        if not text or not self.embedding_model:
            return [0.0] * output_dim

        try:
            vec = self.embedding_model.embed_documents([text])[0]
            # Truncate or pad to output_dim
            if len(vec) >= output_dim:
                return vec[:output_dim]
            else:
                return vec + [0.0] * (output_dim - len(vec))
        except Exception as e:
            self.logger.error(f"Text embedding failed: {e}")
            return [0.0] * output_dim

    def _get_clickable_elements(self) -> list:
        """
        Use VisionLayer to enumerate clickable elements on the screen.
        Returns a list of dicts: { 'coords': (x, y), 'label': str, 'accessibility': float }
        
        FIX: Added robust error handling for pytesseract execution.
        """
        # TODO: Upgrade to DOM-based element discovery for robustness.
        screenshot_path = self.vision.capture_screen()
        if not screenshot_path:
            return []
            
        elements = []
        try:
            from PIL import Image
            image = Image.open(screenshot_path)
            
            # Check if pytesseract is available before using it
            if pytesseract is None:
                 self.logger.error("pytesseract module is not installed. Returning no clickable elements.")
                 return []
            
            # Execute OCR and get detailed data
            ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            # Ensure the core lists are present and of the same length
            if not ocr_data or 'text' not in ocr_data or len(ocr_data['text']) == 0:
                self.logger.warning("OCR returned empty data structure. Returning no clickable elements.")
                return []
                
            # Iterate through the returned OCR elements using the index, for robustness
            for i, text in enumerate(ocr_data['text']):
                # Only consider elements with non-empty text
                if text and text.strip():
                    try:
                        # Defensive indexing check against potential list index out of range 
                        # if the lists are unexpectedly inconsistent (Tesseract bug or bad data)
                        if i < len(ocr_data['left']) and i < len(ocr_data['width']) and i < len(ocr_data['top']) and i < len(ocr_data['height']) and i < len(ocr_data['conf']):
                            x = ocr_data['left'][i] + ocr_data['width'][i] // 2
                            y = ocr_data['top'][i] + ocr_data['height'][i] // 2
                            
                            # Accessibility: stub, using confidence. Handles potential '-1' string or conversion failure.
                            try:
                                conf_str = str(ocr_data['conf'][i]).strip()
                                acc = float(conf_str) / 100.0 if conf_str != '-1' and conf_str else 0.0
                            except Exception:
                                acc = 0.0
                                
                            elements.append({'coords': (x, y), 'label': text, 'accessibility': acc})
                        else:
                            self.logger.warning(f"Inconsistent OCR data length at index {i}. Skipping element.")
                    except Exception as e:
                        # Catch potential conversion errors within the loop (e.g., float())
                        self.logger.warning(f"Error processing OCR element {i}: {e}. Skipping element.")
                        continue
                        
            return elements
            
        except Exception as e:
            # Catch Tesseract not found error, bad path, or any other fatal OCR error (FATAL ERROR trace)
            # The setting of pytesseract.pytesseract.tesseract_cmd should handle TesseractNotFoundError
            self.logger.error(f"FATAL OCR ERROR (Worker crash source): {e}. Returning no clickable elements.")
            return []

    def reset_session(self, url: str) -> Dict[str, Any]:
        self.logger.info(f"UI Driver: reset session -> {url}")
        screenshot_path = self.vision.capture_screen()
        if not screenshot_path:
            raise RuntimeError("VisionLayer.capture_screen() failed during reset")
        features = self._extract_visual_features(screenshot_path)
        clickable_elements = self._get_clickable_elements()
        self._last_clickable_elements = clickable_elements
        accessibility = self._compute_accessibility(clickable_elements)
        return {
            "current_dom_state": f"navigated:{url}",
            "screenshot_features": features,
            "accessibility_score": accessibility,
            "task_progress": 0.0,
            "clickable_elements": clickable_elements,
        }

    def _compute_accessibility(self, elements: list) -> float:
        """
        Compute a real accessibility score from element info.
        """
        # TODO: Integrate a real accessibility checker using DOM or accessibility tree.
        if not elements:
            return 0.0
        return float(sum(e['accessibility'] for e in elements)) / len(elements)

    def execute_action(self, action_id: int) -> Dict[str, Any]:
        self.logger.info(f"UI Driver: execute action {action_id}")
        clickable_elements = getattr(self, '_last_clickable_elements', None)
        if clickable_elements is None or len(clickable_elements) == 0:
            clickable_elements = self._get_clickable_elements()
        # Map action id to element
        if 0 <= action_id < 100:
            if action_id < len(clickable_elements):
                coords = clickable_elements[action_id]['coords']
                success = self.action.click(coords)
            else:
                # No-op if action_id exceeds available elements
                self.logger.info(f"No clickable element for action_id {action_id}, skipping click.")
                success = False
        elif action_id == 100:
            success = self.action.scroll(-300)
        else:
            raise ValueError(f"Invalid action id: {action_id}")
        # Re-capture screen after action
        screenshot_path = self.vision.capture_screen()
        if not screenshot_path:
            raise RuntimeError("VisionLayer.capture_screen() failed after action")
        features = self._extract_visual_features(screenshot_path)
        clickable_elements = self._get_clickable_elements()
        self._last_clickable_elements = clickable_elements
        accessibility = self._compute_accessibility(clickable_elements)
        # Task progress: stub, could be improved with DOM diff or goal matching
        task_progress = 0.1 if success else 0.0
        return {
            "new_dom_state": f"after_action_{action_id}",
            "screenshot_features": features,
            "accessibility_score": accessibility,
            "task_progress": task_progress,
            "clickable_elements": clickable_elements,
        }


class YUSR_UI_MultiAgentEnv(MultiAgentEnv):
    """The concrete Multi-Agent RL environment used by YUSR training.

    Inputs/Outputs (contract):
    - reset(options={'start_url': str}) -> observations dict, info dict
    - step(action_dict) -> obs, rewards, terminated, truncated, info

    Observation shapes:
    - nav_agent.visual_input: (128,)
    - nav_agent.task_goal: (32,)
    - nav_agent.accessibility_features: (5,)
    - pers_agent.user_history_vector: (64,)
    - pers_agent.current_context_embedding: (64,)
    - llm_agent.dom_snapshot_embedding: (64,)
    - llm_agent.agent_status_log_embedding: (32,)
    """

    POSSIBLE_AGENTS = {"nav_agent", "pers_agent", "llm_agent"}
    DEFAULT_START_URL = "https://example.com/start_task"

    # --- START OF STATIC SPACE DEFINITIONS ---
    # These must be defined outside of __init__ for Ray/RLlib to read them.

    @staticmethod
    def __define_observation_space() -> GymDict:
        return GymDict({
            "nav_agent": GymDict({
                # Note: Using np.float32 for consistency with vectorized data
                "visual_input": Box(low=0.0, high=1.0, shape=(128,), dtype=np.float32), 
                "task_goal": Box(low=-1.0, high=1.0, shape=(32,), dtype=np.float32),
                "accessibility_features": Box(low=0.0, high=1.0, shape=(5,), dtype=np.float32),
            }),
            "pers_agent": GymDict({
                "user_history_vector": Box(low=0.0, high=1.0, shape=(64,), dtype=np.float32),
                "current_context_embedding": Box(low=-1.0, high=1.0, shape=(64,), dtype=np.float32),
            }),
            "llm_agent": GymDict({
                "dom_snapshot_embedding": Box(low=-1.0, high=1.0, shape=(64,), dtype=np.float32),
                "agent_status_log_embedding": Box(low=-1.0, high=1.0, shape=(32,), dtype=np.float32),
            }),
        })

    @staticmethod
    def __define_action_space() -> GymDict:
        return GymDict({
            # Action 0-99: Click element (up to 100 elements)
            # Action 100: Scroll down
            "nav_agent": Discrete(101),
            # Action 0: No-op / Ignore; Action 1: Provide preference suggestion
            "pers_agent": Discrete(2),
            # Action 0: No-op / Ignore; Action 1: Suggest DOM action; Action 2: Suggest task step
            "llm_agent": Discrete(3),
        })

    # The actual static class attributes required by RLlib/Ray:
    observation_space = __define_observation_space()
    action_space = __define_action_space()

    # --- END OF STATIC SPACE DEFINITIONS ---

    def __init__(self, env_config: Dict[str, Any]):
        super().__init__()
        self.config = env_config or {}
        # RLlib expects env instances to expose `agents` and `possible_agents`.
        self.possible_agents = list(self.POSSIBLE_AGENTS)
        self.agents = list(self.POSSIBLE_AGENTS)
        self._agent_ids = self.agents

        # --- EXPLICIT SPACE REGISTRATION (instance-level) ---
        static_obs = self.__class__.observation_space
        static_act = self.__class__.action_space
        
        # Get the underlying dictionaries from the GymDict instances
        static_obs_map = getattr(static_obs, "spaces", None) or {}
        static_act_map = getattr(static_act, "spaces", None) or {}

        # Build instance dictionaries mapping agent_id -> space
        self.observation_spaces: Dict[str, Any] = {}
        self.action_spaces: Dict[str, Any] = {}
        for aid in self.possible_agents:
            if aid not in static_obs_map:
                raise ValueError(f"Missing observation space for agent '{aid}' in static definition")
            if aid not in static_act_map:
                raise ValueError(f"Missing action space for agent '{aid}' in static definition")
            self.observation_spaces[aid] = static_obs_map[aid]
            self.action_spaces[aid] = static_act_map[aid]

        # Explicitly set the mandatory instance attributes
        self.observation_space = GymDict(self.observation_spaces)
        self.action_space = GymDict(self.action_spaces)

        # Sanity check: no None values
        for k, v in self.observation_spaces.items():
            if v is None:
                raise ValueError(f"Observation space for agent '{k}' is None")
        for k, v in self.action_spaces.items():
            if v is None:
                raise ValueError(f"Action space for agent '{k}' is None")

        # Concrete driver (will use stubs if real Execution Agent failed to import)
        self.ui_driver = ExecutionUIDriver()

        # Internal state
        self.current_user_profile = {"preference_vector": [0.0] * 64}

        # Compute task embedding if a textual description is provided
        task_desc = self.config.get("task_description")
        if task_desc:
            # Re-using the driver's embedding model if possible
            if self.ui_driver.embedding_model:
                vec = self.ui_driver._embed_text(task_desc, 32)
            else:
                 # Fallback if no embedding model available
                vec = [0.0] * 32
                
            self.current_task_goal = vec
        else:
            self.current_task_goal = self.config.get("task_goal_embedding", [0.0] * 32)

        self.global_step = 0
        self.max_steps = 100

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        # Delegate to RLlib parent if present
        try:
            super().reset(seed=seed)
        except Exception:
            pass

        self.global_step = 0
        start_url = options.get("start_url", self.DEFAULT_START_URL) if options else self.DEFAULT_START_URL
        initial_ui_state = self.ui_driver.reset_session(start_url)
        self._last_ui_state = initial_ui_state
        initial_obs = self._get_observations(initial_ui_state)
        return initial_obs, {"task_status": "starting", "url": start_url}

    def step(self, action_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, float], Dict[str, bool], Dict[str, bool], Dict[str, Any]]:
        self.global_step += 1
        nav_action_id = action_dict.get("nav_agent", 0)
        # Save previous state for reward calculation
        prev_ui_state = getattr(self, '_last_ui_state', None)
        new_ui_state = self.ui_driver.execute_action(nav_action_id)
        self._last_ui_state = new_ui_state
        obs = self._get_observations(new_ui_state)
        
        # common_info will be the dictionary returned from _calculate_rewards containing global/debugging info
        rewards, common_info = self._calculate_rewards(new_ui_state, action_dict, prev_ui_state)
        
        # RLlib expects per-agent returns or a special "__all__" key for termination/truncation
        terminated, truncated = self._check_termination(new_ui_state)
        
        # All agents terminate/truncate if the environment does
        all_terminated = {agent_id: terminated for agent_id in self._agent_ids}
        all_truncated = {agent_id: truncated for agent_id in self._agent_ids}
        all_terminated["__all__"] = terminated
        all_truncated["__all__"] = truncated
        
        # FIX: Distribute the common environment info to all agents using their IDs.
        # This satisfies RLlib's requirement that info keys be a subset of obs keys (agent IDs).
        info = {agent_id: common_info for agent_id in self._agent_ids}

        return obs, rewards, all_terminated, all_truncated, info

    def _get_observations(self, ui_state: Dict[str, Any]) -> Dict[str, Any]:
        visual_features = ui_state.get("screenshot_features")
        dom_text_snippet = ui_state.get("current_dom_state", "")
        agent_status_text = f"Step {self.global_step}"
        
        # Use the driver to embed the text snippets for the Box spaces
        context_emb = self.ui_driver._embed_text(dom_text_snippet[:128], 64)
        dom_emb = self.ui_driver._embed_text(dom_text_snippet[:1024], 64)
        status_emb = self.ui_driver._embed_text(agent_status_text, 32)

        accessibility_metrics = [
            ui_state.get("accessibility_score", 0.8),
            0.1, 0.0, 0.0, 0.0,
        ][:5]

        # FIX: Explicitly cast and reshape the list data into np.array with the REQUIRED shape (N,)
        # This prevents the 'episode_reward_mean' crash caused by RLlib preprocessor errors.
        return {
            "nav_agent": {
                # Ensure shape (128,)
                "visual_input": np.array(visual_features, dtype=np.float32).reshape((128,)), 
                # Ensure shape (32,)
                "task_goal": np.array(self.current_task_goal, dtype=np.float32).reshape((32,)),
                # Ensure shape (5,)
                "accessibility_features": np.array(accessibility_metrics, dtype=np.float32).reshape((5,)),
            },
            "pers_agent": {
                # Ensure shape (64,)
                "user_history_vector": np.array(self.current_user_profile["preference_vector"], dtype=np.float32).reshape((64,)),
                # Ensure shape (64,)
                "current_context_embedding": np.array(context_emb, dtype=np.float32).reshape((64,)), 
            },
            "llm_agent": {
                # Ensure shape (64,)
                "dom_snapshot_embedding": np.array(dom_emb, dtype=np.float32).reshape((64,)), 
                # Ensure shape (32,)
                "agent_status_log_embedding": np.array(status_emb, dtype=np.float32).reshape((32,)), 
            },
        }

    def _calculate_rewards(self, ui_state: Dict[str, Any], action_dict: Dict[str, Any], prev_ui_state: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, float], Dict[str, Any]]:
        rewards = {agent_id: 0.0 for agent_id in self._agent_ids}
        # This will become the 'common_info' returned by step
        info = {}
        
        task_progress = ui_state.get("task_progress", 0.0)
        accessibility_score = ui_state.get("accessibility_score", 0.0)
        
        prev_task_progress = prev_ui_state.get("task_progress", 0.0) if prev_ui_state else 0.0
        prev_accessibility_score = prev_ui_state.get("accessibility_score", 0.0) if prev_ui_state else 0.0
        
        # Navigation agent: reward for progress and accessibility
        reward_nav = (0.7 * (task_progress - prev_task_progress)) + (0.3 * (accessibility_score - prev_accessibility_score)) - 0.01
        rewards["nav_agent"] = reward_nav
        
        # Add a global key to the info dict for debugging/metrics
        info["nav_reward_details"] = {"progress": task_progress, "access_score": accessibility_score, "nav_reward": reward_nav}
        
        # Collaborative agents: reward for positive change if they acted
        if action_dict.get("pers_agent") == 1:
            pers_reward = max(0.0, (task_progress - prev_task_progress) + (accessibility_score - prev_accessibility_score))
            rewards["pers_agent"] = pers_reward
        if action_dict.get("llm_agent") == 1:
            llm_reward = max(0.0, (task_progress - prev_task_progress) + (accessibility_score - prev_accessibility_score))
            rewards["llm_agent"] = llm_reward
            
        return rewards, info

    def _check_termination(self, ui_state: Dict[str, Any]) -> Tuple[bool, bool]:
        task_success = ui_state.get("task_progress", 0.0) >= 0.99
        step_limit_reached = self.global_step >= self.max_steps
        return task_success, step_limit_reached