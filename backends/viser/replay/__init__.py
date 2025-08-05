"""
Robot Replay System for Viser Backend

This module provides both streaming and offline replay functionality:

- Streaming: Real-time data processing and playback (current implementation)
- Offline: Pre-processed, lag-free replay with instant seeking (new implementation)

Both modes share common components like DataParser and JointMapper while
implementing different replay strategies optimized for their use cases.

Usage:
    # Streaming replay (existing)
    from backends.viser.replay.streaming import StreamingManager
    
    # Offline replay (new - lag-free)  
    from backends.viser.replay.offline import OfflineManager
    
    # Shared components
    from backends.viser.replay import DataParser, JointMapper
"""

# Shared components
from .parser import DataParser
from .joint_mapper import JointMapper

# Streaming replay (existing functionality)
from .streaming import StreamingManager as StreamingReplayManager
from .streaming import create_streaming_manager

# Offline replay (new functionality)
from .offline import OfflineManager as OfflineReplayManager
from .offline import create_offline_manager

__all__ = [
    'DataParser',
    'JointMapper',
    'StreamingReplayManager', 
    'create_streaming_manager',
    'OfflineReplayManager',
    'create_offline_manager'
]
