"""
Offline Replay System - Lag-Free Robot Data Playback

This module implements offline replay with two-phase processing:

Phase 1: Pre-processing (upfront cost ~30s)
- Parse ALL robot data at once  
- Pre-compute ALL joint configurations
- Buffer everything in memory as NumPy arrays

Phase 2: Ultra-fast playback (zero latency)
- Just array indexing for frame access
- Instant seeking to any frame
- Variable speed playback
- Frame-perfect controls

Usage:
    # Use through the main replay system
    from backends.viser.replay import create_replay_system
    replay_system = create_replay_system(server, urdf_manager)
    replay_system.setup(robot_data=1)
"""

from .processor import OfflineProcessor
from .controller import OfflineController  

__all__ = [
    'OfflineProcessor',
    'OfflineController'
]
