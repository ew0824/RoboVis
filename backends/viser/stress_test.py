"""
Stress Testing Module for Viser Backend Performance Testing

This module provides high-frequency stress testing capabilities to simulate
real-world robot operation loads and measure system performance under stress.
It generates sinusoidal joint motions at configurable frequencies to test
the limits of the visualization and telemetry systems.

Features:
- Configurable stress test frequency (Hz)
- Adjustable motion amplitude and wave characteristics
- Selective joint testing (test subset of joints)
- Real-time GUI controls with start/stop functionality
- Thread-safe execution with clean shutdown
- Performance monitoring integration

Usage:
    from stress_test import StressTestManager
    
    # Create stress test manager
    stress_manager = StressTestManager(server, urdf_manager)
    
    # Add GUI controls
    stress_manager.add_stress_controls()
    
    # Stress testing can then be controlled via GUI
"""

from __future__ import annotations

import time
import threading
from typing import Optional

import numpy as np
import viser

from telemetry import publish_telemetry


class StressTestManager:
    """
    Manages high-frequency stress testing for the Viser backend.
    
    This class provides comprehensive stress testing functionality including
    sinusoidal motion generation, GUI controls, and performance monitoring.
    It can stress test a configurable number of joints at various frequencies
    to identify system performance limits and bottlenecks.
    
    Attributes:
        server: Viser server instance for GUI controls
        urdf_manager: SmartUrdfManager instance for robot control
        stress_thread: Thread running the stress testing loop
        stress_running: Event to control stress testing execution
        stress_hz: Current stress testing frequency in Hz
        stress_amplitude: Current joint motion amplitude in radians
        stress_wave_freq: Frequency of the sinusoidal wave motion
        stress_joints: Number of joints to stress test
        initial_config: Initial robot configuration for stress testing
    """
    
    def __init__(self, server: viser.ViserServer, urdf_manager, initial_config: np.ndarray):
        """
        Initialize the stress test manager.
        
        Args:
            server: Viser server instance
            urdf_manager: SmartUrdfManager instance
            initial_config: Initial joint configuration array
        """
        self.server = server
        self.urdf_manager = urdf_manager
        self.initial_config = initial_config
        
        # Stress testing state
        self.stress_thread: Optional[threading.Thread] = None
        self.stress_running = threading.Event()
        
        # Default stress testing parameters
        self.stress_hz = 200.0
        self.stress_amplitude = 0.3
        self.stress_wave_freq = 0.3
        self.stress_joints = None  # None means all joints
        
        # GUI controls (will be set when controls are added)
        self.stress_enabled_cb = None
        self.stress_hz_slider = None
        self.stress_amplitude_slider = None
        self.stress_info = None
        
        print(f"[STRESS] Stress test manager initialized")
        
    def add_stress_controls(self) -> None:
        """
        Add stress testing controls to the Viser GUI.
        
        Creates a dedicated folder with controls for:
        - Enable/disable stress testing
        - Frequency adjustment
        - Amplitude adjustment
        - Status display
        
        The controls are dynamically updated and provide real-time feedback.
        """
        meaningful_dof = self.urdf_manager.get_total_meaningful_dof()
        nq = self.stress_joints if self.stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        with self.server.gui.add_folder("Stress Testing"):
            # Main enable/disable control
            self.stress_enabled_cb = self.server.gui.add_checkbox("Enable Stress Testing", False)
            
            # Frequency control
            self.stress_hz_slider = self.server.gui.add_slider(
                "Frequency (Hz)",
                min=1.0,
                max=500.0,
                step=1.0,
                initial_value=self.stress_hz,
            )
            
            # Amplitude control
            self.stress_amplitude_slider = self.server.gui.add_slider(
                "Amplitude (rad)",
                min=0.1,
                max=1.5,
                step=0.1,
                initial_value=self.stress_amplitude,
            )
            
            # Status display
            self.stress_info = self.server.gui.add_text("Status", "Disabled")
            
            # Wire up callbacks
            self.stress_enabled_cb.on_update(self._on_stress_enabled_change)
            self.stress_hz_slider.on_update(self._on_stress_hz_change)
            self.stress_amplitude_slider.on_update(self._on_stress_amplitude_change)
            
        print(f"[STRESS] Stress testing controls added to GUI")
        print(f"[STRESS] Config: {self.stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints, ±{self.stress_amplitude:.2f}rad")
        
    def _on_stress_enabled_change(self, _) -> None:
        """Handle stress testing enable/disable toggle."""
        if self.stress_enabled_cb.value and self.stress_thread is None:
            # Start stress testing
            self.start_stress_testing()
        elif not self.stress_enabled_cb.value and self.stress_thread is not None:
            # Stop stress testing
            self.stop_stress_testing()
            
    def _on_stress_hz_change(self, _) -> None:
        """Handle stress testing frequency change."""
        self.stress_hz = self.stress_hz_slider.value
        if self.stress_thread is not None:
            self._update_status_display()
            
    def _on_stress_amplitude_change(self, _) -> None:
        """Handle stress testing amplitude change."""
        self.stress_amplitude = self.stress_amplitude_slider.value
        if self.stress_thread is not None:
            self._update_status_display()
            
    def start_stress_testing(self) -> None:
        """
        Start the stress testing thread.
        
        Creates and starts a new thread running the stress testing loop
        with the current parameters. The thread generates sinusoidal
        motion and updates the robot configuration at the specified frequency.
        """
        if self.stress_thread is not None:
            print("[STRESS] Warning: Stress testing already running")
            return
            
        meaningful_dof = self.urdf_manager.get_total_meaningful_dof()
        nq = self.stress_joints if self.stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        print(f"🚀 [STRESS] Starting stress testing:")
        print(f"   Meaningful DOF: {meaningful_dof}")
        print(f"   Stress joints: {nq}")
        print(f"   Frequency: {self.stress_hz:.1f} Hz")
        print(f"   Amplitude: ±{self.stress_amplitude:.2f} rad")
        print(f"   Wave frequency: {self.stress_wave_freq:.2f} Hz")
        
        self.stress_running.set()
        self.stress_thread = threading.Thread(
            target=self._stress_testing_loop,
            args=(nq,),
            daemon=True
        )
        self.stress_thread.start()
        
        self._update_status_display()
        
    def stop_stress_testing(self) -> None:
        """
        Stop the stress testing thread.
        
        Signals the stress testing thread to stop and waits for clean shutdown.
        Updates the GUI status to reflect the stopped state.
        """
        if self.stress_thread is None:
            return
            
        print("⏹️ [STRESS] Stopping stress testing")
        self.stress_running.clear()
        
        # Wait for thread to finish
        if self.stress_thread.is_alive():
            self.stress_thread.join(timeout=1.0)
            
        self.stress_thread = None
        
        if self.stress_info:
            self.stress_info.value = "Disabled"
            
    def _stress_testing_loop(self, nq: int) -> None:
        """
        Main stress testing loop that generates sinusoidal motion.
        
        Args:
            nq: Number of joints to stress test
            
        This method runs in a separate thread and continuously generates
        sinusoidal joint motions, updates the robot configuration, and
        publishes telemetry data. It maintains the specified frequency
        and provides performance statistics.
        """
        print(f"🔥 [STRESS] Stress testing loop started with {nq} joints")
        
        # Generate phase offsets for smooth multi-joint motion
        phases = np.linspace(0, 2*np.pi, nq, endpoint=False)
        
        # Initialize timing
        t0 = time.perf_counter()
        msg_count = 0
        last_stats = t0
        
        try:
            while self.stress_running.is_set():
                loop_start = time.perf_counter()
                
                # Get current parameters (they can change during execution)
                hz = self.stress_hz
                amplitude = self.stress_amplitude
                wave_freq = self.stress_wave_freq
                
                # Generate sinusoidal motion for selected joints
                t = loop_start - t0
                stress_values = amplitude * np.sin(2*np.pi*wave_freq*t + phases)
                
                # Create full configuration (stress values + initial values for other joints)
                full_config = self.initial_config.copy()
                full_config[:nq] = stress_values
                
                # Update all URDFs and coordinate frames
                self.urdf_manager.update_all_configurations(full_config)
                publish_telemetry(full_config)
                msg_count += 1
                
                # Print statistics periodically
                if loop_start - last_stats >= 10.0:
                    elapsed = loop_start - t0
                    avg_hz = msg_count / elapsed if elapsed > 0 else 0
                    print(f"🔥 [STRESS] {msg_count:,} updates | {elapsed:.1f}s | {avg_hz:.1f} Hz avg | Target: {hz:.1f} Hz | {nq} DOF")
                    last_stats = loop_start
                
                # Sleep to maintain frequency
                period = 1.0 / hz if hz > 0 else 1.0
                loop_end = time.perf_counter()
                sleep_time = period - (loop_end - loop_start)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            print(f"[STRESS] Error in stress testing loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("⏹️ [STRESS] Stress testing loop finished")
            
    def _update_status_display(self) -> None:
        """Update the GUI status display with current parameters."""
        if self.stress_info is None:
            return
            
        meaningful_dof = self.urdf_manager.get_total_meaningful_dof()
        nq = self.stress_joints if self.stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        if self.stress_thread is not None:
            self.stress_info.value = f"🔥 ACTIVE - {self.stress_hz:.1f}Hz, {nq}/{meaningful_dof} joints, ±{self.stress_amplitude:.2f}rad"
        else:
            self.stress_info.value = "Disabled"
            
    def set_stress_joints(self, num_joints: Optional[int]) -> None:
        """
        Set the number of joints to stress test.
        
        Args:
            num_joints: Number of joints to test, None for all joints
            
        This method allows dynamic adjustment of the number of joints
        being stress tested, useful for scaling performance tests.
        """
        meaningful_dof = self.urdf_manager.get_total_meaningful_dof()
        
        if num_joints is None:
            self.stress_joints = None
            print(f"[STRESS] Set to stress test all {meaningful_dof} joints")
        else:
            self.stress_joints = min(num_joints, meaningful_dof)
            print(f"[STRESS] Set to stress test {self.stress_joints} of {meaningful_dof} joints")
            
        self._update_status_display()
        
    def get_stress_status(self) -> dict:
        """
        Get current stress testing status.
        
        Returns:
            Dictionary with stress testing status information including:
            - is_running: Whether stress testing is active
            - frequency: Current frequency setting
            - amplitude: Current amplitude setting
            - joints_tested: Number of joints being tested
            - total_joints: Total number of meaningful joints available
        """
        meaningful_dof = self.urdf_manager.get_total_meaningful_dof()
        nq = self.stress_joints if self.stress_joints is not None else meaningful_dof
        nq = min(nq, meaningful_dof)
        
        return {
            "is_running": self.stress_thread is not None,
            "frequency": self.stress_hz,
            "amplitude": self.stress_amplitude,
            "wave_frequency": self.stress_wave_freq,
            "joints_tested": nq,
            "total_joints": meaningful_dof
        }
        
    def cleanup(self) -> None:
        """
        Clean up resources and stop stress testing.
        
        This method should be called when shutting down to ensure
        the stress testing thread is properly terminated.
        """
        if self.stress_thread is not None:
            print("[STRESS] Cleaning up stress testing resources")
            self.stop_stress_testing()


def create_stress_test_manager(server: viser.ViserServer, urdf_manager, initial_config: np.ndarray) -> StressTestManager:
    """
    Factory function to create a StressTestManager instance.
    
    Args:
        server: Viser server instance
        urdf_manager: SmartUrdfManager instance
        initial_config: Initial joint configuration
        
    Returns:
        Configured StressTestManager instance
        
    This factory function provides a convenient way to create and configure
    a stress test manager with sensible defaults.
    """
    return StressTestManager(server, urdf_manager, initial_config)
