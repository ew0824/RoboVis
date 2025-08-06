"""
Robot Replay System for Viser Backend

This module provides the new unified replay system with both streaming 
and offline replay functionality through a clean coordinator interface.

Usage:
    # Main replay system (recommended)
    from backends.viser.replay import create_replay_system
    replay_system = create_replay_system(server, urdf_manager)
    replay_system.setup(robot_data=1)
    
    # Individual components (advanced usage)
    from backends.viser.replay.streaming.controller import StreamingController
    from backends.viser.replay.offline.controller import OfflineController
"""

# Main replay system
from .replay import ReplayCoordinator, create_replay_system

# Individual controllers (for advanced usage)
from .streaming.controller import StreamingController
from .offline.controller import OfflineController

# Shared components
from .parser import DataParser
from .joint_mapper import JointMapper

__all__ = [
    'ReplayCoordinator',
    'create_replay_system',
    'StreamingController',
    'OfflineController', 
    'DataParser',
    'JointMapper'
]
