"""
Offline Replay System - Lag-Free Robot Data Playback

This module implements true offline replay with two-phase processing:

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
    from backends.viser.replay.offline import OfflineManager
    
    # Create and initialize (handles both phases)
    offline_manager = OfflineManager(server, urdf_manager, robot_data=1)
    await offline_manager.initialize_async(downsample=5)
"""

from .processor import OfflineProcessor
from .controller import OfflineController  
from .manager import OfflineManager, create_offline_manager

__all__ = [
    'OfflineProcessor',
    'OfflineController', 
    'OfflineManager',
    'create_offline_manager'
]
