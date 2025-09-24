#!/usr/bin/env python3
"""
Web Interface Integration for Configurable Feedrates

This file shows how to integrate the new feedrate configuration system into the web interface.
It demonstrates setting operating modes and using intelligent feedrate selection for jog commands.

Author: Scanner System Redesign  
Created: September 24, 2025
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WebInterfaceFeedrateManager:
    """
    Manages feedrate configuration for web interface operations
    
    Provides methods to:
    - Switch between manual and scanning modes
    - Get optimal feedrates for different operations
    - Handle user feedrate preferences
    - Validate feedrate settings
    """
    
    def __init__(self, motion_controller):
        """Initialize with motion controller reference"""
        self.motion_controller = motion_controller
        self.logger = logging.getLogger(__name__)
        
        # Ensure controller starts in manual mode for web interface
        if hasattr(motion_controller, 'set_operating_mode'):
            motion_controller.set_operating_mode('manual_mode')
            self.logger.info("🌐 Web interface initialized in manual_mode for responsive jog commands")
    
    def set_mode_for_operation(self, operation_type: str) -> bool:
        """
        Set appropriate operating mode based on operation type
        
        Args:
            operation_type: 'jog', 'manual', 'scan', 'auto', 'positioning'
            
        Returns:
            bool: True if mode was set successfully
        """
        if not hasattr(self.motion_controller, 'set_operating_mode'):
            self.logger.warning("Motion controller doesn't support operating modes")
            return False
        
        # Map operation types to modes
        mode_mapping = {
            'jog': 'manual_mode',         # Web jog buttons
            'manual': 'manual_mode',      # Manual positioning
            'positioning': 'manual_mode', # Manual position entry
            'scan': 'scanning_mode',      # Automated scanning
            'auto': 'scanning_mode',      # Automated operations
            'scan_prep': 'scanning_mode'  # Scan preparation moves
        }
        
        mode = mode_mapping.get(operation_type, 'manual_mode')
        success = self.motion_controller.set_operating_mode(mode)
        
        if success:
            self.logger.info(f"🔧 Web interface mode: {operation_type} → {mode}")
        else:
            self.logger.error(f"❌ Failed to set mode for operation: {operation_type}")
            
        return success
    
    def get_jog_feedrate(self, axis: str, distance: float = 1.0) -> float:
        """
        Get optimal feedrate for jog operations
        
        Args:
            axis: 'x', 'y', 'z', or 'c'
            distance: Distance of jog (for adjustment)
            
        Returns:
            float: Optimal feedrate for the jog
        """
        if not hasattr(self.motion_controller, 'get_feedrate_for_axis'):
            # Fallback feedrates if controller doesn't support configuration
            fallback_feedrates = {'x': 300.0, 'y': 300.0, 'z': 200.0, 'c': 1000.0}
            return fallback_feedrates.get(axis.lower(), 100.0)
        
        # Ensure we're in manual mode for jog operations
        self.set_mode_for_operation('jog')
        
        # Get base feedrate for axis
        base_feedrate = self.motion_controller.get_feedrate_for_axis(axis.lower())
        
        # Adjust for very small jogs (can be faster)
        if abs(distance) < 0.1:
            adjustment_factor = 1.2  # 20% faster for small precise jogs
        elif abs(distance) > 5.0:
            adjustment_factor = 0.8  # 20% slower for large jogs (safety)
        else:
            adjustment_factor = 1.0  # Normal speed
        
        adjusted_feedrate = base_feedrate * adjustment_factor
        
        # Validate against axis limits
        if hasattr(self.motion_controller, 'limits'):
            axis_limits = self.motion_controller.limits.get(axis.lower())
            if axis_limits and hasattr(axis_limits, 'max_feedrate'):
                adjusted_feedrate = min(adjusted_feedrate, axis_limits.max_feedrate)
        
        self.logger.debug(f"🎯 Jog feedrate: {axis} {distance}mm → {adjusted_feedrate}")
        return adjusted_feedrate
    
    def get_manual_positioning_feedrate(self, position_delta) -> float:
        """
        Get feedrate for manual positioning moves (Go To Position)
        
        Args:
            position_delta: Position4D or dict with movement delta
            
        Returns:
            float: Optimal feedrate for the positioning move
        """
        if not hasattr(self.motion_controller, 'get_optimal_feedrate'):
            return 200.0  # Conservative fallback
        
        # Ensure manual mode for positioning
        self.set_mode_for_operation('positioning')
        
        # Get optimal feedrate from controller
        optimal_feedrate = self.motion_controller.get_optimal_feedrate(position_delta)
        
        self.logger.debug(f"🎯 Manual positioning feedrate: {optimal_feedrate}")
        return optimal_feedrate
    
    def get_scan_preparation_feedrate(self) -> Dict[str, float]:
        """
        Get feedrates for scan preparation moves (slower, precise)
        
        Returns:
            Dict[str, float]: Feedrates for each axis during scan prep
        """
        if not hasattr(self.motion_controller, 'get_current_feedrates'):
            return {'x': 100.0, 'y': 100.0, 'z': 50.0, 'c': 200.0}
        
        # Switch to scanning mode for preparation
        self.set_mode_for_operation('scan_prep')
        
        # Get scanning mode feedrates
        scan_feedrates = self.motion_controller.get_current_feedrates()
        
        self.logger.info(f"🔧 Scan preparation feedrates: {scan_feedrates}")
        return scan_feedrates
    
    def get_current_mode_info(self) -> Dict[str, Any]:
        """Get current operating mode and feedrate information"""
        if not hasattr(self.motion_controller, 'get_operating_mode'):
            return {
                'mode': 'unknown',
                'feedrates': {'x': 100.0, 'y': 100.0, 'z': 100.0, 'c': 100.0},
                'description': 'Controller does not support mode configuration'
            }
        
        current_mode = self.motion_controller.get_operating_mode()
        current_feedrates = self.motion_controller.get_current_feedrates()
        
        # Get mode description from configuration
        all_configs = self.motion_controller.get_all_feedrate_configurations()
        description = all_configs.get(current_mode, {}).get('description', 'No description available')
        
        return {
            'mode': current_mode,
            'feedrates': current_feedrates,
            'description': description,
            'available_modes': list(all_configs.keys()) if all_configs else []
        }
    
    def update_feedrate_preference(self, axis: str, mode: str, feedrate: float) -> Dict[str, Any]:
        """
        Update user feedrate preference
        
        Args:
            axis: 'x_axis', 'y_axis', 'z_axis', or 'c_axis'
            mode: 'manual_mode' or 'scanning_mode'
            feedrate: New feedrate value
            
        Returns:
            Dict with result information
        """
        if not hasattr(self.motion_controller, 'update_feedrate_config'):
            return {
                'success': False,
                'message': 'Controller does not support runtime feedrate updates'
            }
        
        success = self.motion_controller.update_feedrate_config(mode, axis, feedrate)
        
        if success:
            self.logger.info(f"🔧 User updated feedrate: {mode}.{axis} → {feedrate}")
            return {
                'success': True,
                'message': f'Updated {axis} feedrate to {feedrate} for {mode}',
                'new_feedrates': self.motion_controller.get_current_feedrates()
            }
        else:
            return {
                'success': False,
                'message': 'Failed to update feedrate - check axis/mode names and limits'
            }


def enhance_web_interface_jog_endpoint(web_interface_instance):
    """
    Enhance existing web interface with improved jog functionality
    
    This function modifies the existing web interface to use the new feedrate system.
    Call this during web interface initialization.
    """
    
    # Add feedrate manager to web interface
    if hasattr(web_interface_instance, 'orchestrator') and web_interface_instance.orchestrator:
        if hasattr(web_interface_instance.orchestrator, 'motion_controller'):
            web_interface_instance.feedrate_manager = WebInterfaceFeedrateManager(
                web_interface_instance.orchestrator.motion_controller
            )
            logger.info("✅ Feedrate manager added to web interface")
        else:
            logger.warning("⚠️ Motion controller not available - using fallback feedrates")
            web_interface_instance.feedrate_manager = None
    
    # Store original jog method
    original_execute_jog = web_interface_instance._execute_jog_command
    
    async def enhanced_execute_jog_command(delta_values: Dict[str, float], speed: Optional[float] = None) -> Dict[str, Any]:
        """Enhanced jog command with intelligent feedrate selection"""
        try:
            # Use feedrate manager if available
            if hasattr(web_interface_instance, 'feedrate_manager') and web_interface_instance.feedrate_manager:
                feedrate_manager = web_interface_instance.feedrate_manager
                
                # If no speed provided, calculate optimal feedrate
                if speed is None:
                    # Find the primary moving axis for feedrate selection
                    primary_axis = 'x'  # Default
                    max_movement = 0.0
                    
                    for axis, delta in delta_values.items():
                        if abs(delta) > max_movement:
                            max_movement = abs(delta)
                            primary_axis = axis
                    
                    # Get optimal feedrate for the primary moving axis
                    speed = feedrate_manager.get_jog_feedrate(primary_axis, max_movement)
                    logger.info(f"🎯 Auto-selected jog feedrate: {speed} for {primary_axis} axis ({max_movement}mm)")
                
                # Ensure we're in manual mode for jog operations
                feedrate_manager.set_mode_for_operation('jog')
            
            # Use provided speed or fallback
            if speed is None:
                speed = 200.0  # Conservative fallback
            
            # Execute with selected feedrate
            return await original_execute_jog(delta_values, speed)
            
        except Exception as e:
            logger.error(f"❌ Enhanced jog command failed: {e}")
            # Fallback to original method
            return await original_execute_jog(delta_values, speed or 100.0)
    
    # Replace the method
    web_interface_instance._execute_jog_command = enhanced_execute_jog_command
    logger.info("✅ Web interface jog commands enhanced with intelligent feedrate selection")
    
    # Add new API endpoints for feedrate management
    add_feedrate_api_endpoints(web_interface_instance)


def add_feedrate_api_endpoints(web_interface_instance):
    """Add new API endpoints for feedrate management"""
    
    app = web_interface_instance.app
    
    @app.route('/api/feedrate/mode', methods=['GET', 'POST'])
    def api_feedrate_mode():
        """Get or set operating mode"""
        try:
            if not hasattr(web_interface_instance, 'feedrate_manager') or not web_interface_instance.feedrate_manager:
                return jsonify({'error': 'Feedrate manager not available'}), 500
            
            feedrate_manager = web_interface_instance.feedrate_manager
            
            if request.method == 'GET':
                # Get current mode info
                mode_info = feedrate_manager.get_current_mode_info()
                return jsonify(mode_info)
            
            elif request.method == 'POST':
                # Set operating mode
                data = request.get_json()
                operation_type = data.get('operation_type', 'manual')
                
                success = feedrate_manager.set_mode_for_operation(operation_type)
                
                if success:
                    return jsonify({
                        'success': True,
                        'mode_info': feedrate_manager.get_current_mode_info()
                    })
                else:
                    return jsonify({'error': 'Failed to set operating mode'}), 400
                    
        except Exception as e:
            logger.error(f"Feedrate mode API error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/feedrate/config', methods=['GET', 'POST'])
    def api_feedrate_config():
        """Get or update feedrate configuration"""
        try:
            if not hasattr(web_interface_instance, 'feedrate_manager') or not web_interface_instance.feedrate_manager:
                return jsonify({'error': 'Feedrate manager not available'}), 500
            
            feedrate_manager = web_interface_instance.feedrate_manager
            
            if request.method == 'GET':
                # Get all feedrate configurations
                if hasattr(feedrate_manager.motion_controller, 'get_all_feedrate_configurations'):
                    all_configs = feedrate_manager.motion_controller.get_all_feedrate_configurations()
                    return jsonify(all_configs)
                else:
                    return jsonify({'error': 'Configuration not available'}), 500
            
            elif request.method == 'POST':
                # Update feedrate configuration
                data = request.get_json()
                axis = data.get('axis')
                mode = data.get('mode', 'manual_mode')
                feedrate = data.get('feedrate')
                
                if not all([axis, feedrate]):
                    return jsonify({'error': 'Missing axis or feedrate'}), 400
                
                result = feedrate_manager.update_feedrate_preference(axis, mode, float(feedrate))
                
                if result['success']:
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                    
        except Exception as e:
            logger.error(f"Feedrate config API error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/feedrate/optimal', methods=['POST'])
    def api_optimal_feedrate():
        """Get optimal feedrate for a movement"""
        try:
            if not hasattr(web_interface_instance, 'feedrate_manager') or not web_interface_instance.feedrate_manager:
                return jsonify({'error': 'Feedrate manager not available'}), 500
            
            data = request.get_json()
            operation_type = data.get('operation_type', 'jog')
            movement = data.get('movement', {})
            
            feedrate_manager = web_interface_instance.feedrate_manager
            
            if operation_type == 'jog':
                # Single axis jog
                axis = data.get('axis', 'x')
                distance = data.get('distance', 1.0)
                optimal_feedrate = feedrate_manager.get_jog_feedrate(axis, distance)
                
                return jsonify({
                    'optimal_feedrate': optimal_feedrate,
                    'operation_type': operation_type,
                    'axis': axis,
                    'distance': distance
                })
            
            elif operation_type == 'positioning':
                # Multi-axis positioning
                if hasattr(feedrate_manager.motion_controller, 'get_optimal_feedrate'):
                    # Create position delta object
                    from motion.base import Position4D
                    position_delta = Position4D(
                        x=movement.get('x', 0.0),
                        y=movement.get('y', 0.0),
                        z=movement.get('z', 0.0),
                        c=movement.get('c', 0.0)
                    )
                    
                    optimal_feedrate = feedrate_manager.get_manual_positioning_feedrate(position_delta)
                    
                    return jsonify({
                        'optimal_feedrate': optimal_feedrate,
                        'operation_type': operation_type,
                        'movement': movement
                    })
                else:
                    return jsonify({'error': 'Optimal feedrate calculation not available'}), 500
            
            else:
                return jsonify({'error': f'Unknown operation type: {operation_type}'}), 400
                
        except Exception as e:
            logger.error(f"Optimal feedrate API error: {e}")
            return jsonify({'error': str(e)}), 500
    
    logger.info("✅ Feedrate management API endpoints added to web interface")


# Usage example for integration into existing web interface
def integrate_feedrate_system(web_interface_instance):
    """
    Complete integration of feedrate system into web interface
    
    Call this function during web interface initialization to add all
    feedrate management capabilities.
    """
    logger.info("🔧 Integrating feedrate configuration system into web interface...")
    
    try:
        # Enhance jog commands with intelligent feedrate selection
        enhance_web_interface_jog_endpoint(web_interface_instance)
        
        # Add new API endpoints for feedrate management
        # (already done in enhance_web_interface_jog_endpoint)
        
        logger.info("✅ Feedrate system integration complete!")
        logger.info("")
        logger.info("🌐 NEW WEB INTERFACE CAPABILITIES:")
        logger.info("  • Intelligent feedrate selection for jog commands")
        logger.info("  • Automatic mode switching (manual vs scanning)")
        logger.info("  • Runtime feedrate configuration via API")
        logger.info("  • Optimal feedrate calculation for different operations")
        logger.info("")
        logger.info("🔧 NEW API ENDPOINTS:")
        logger.info("  • GET/POST /api/feedrate/mode - Operating mode management")
        logger.info("  • GET/POST /api/feedrate/config - Feedrate configuration")
        logger.info("  • POST /api/feedrate/optimal - Optimal feedrate calculation")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Feedrate system integration failed: {e}")
        return False


if __name__ == "__main__":
    # Test the feedrate manager functionality
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Web Interface Feedrate Integration Test")
    print("This module provides intelligent feedrate management for web interface jog commands.")
    print("")
    print("Key Features:")
    print("• Automatic feedrate selection based on operation type")
    print("• Per-axis feedrate optimization")
    print("• Runtime feedrate configuration")
    print("• Mode switching (manual vs scanning)")
    print("")
    print("Integration: Call integrate_feedrate_system(web_interface_instance)")
    print("during web interface initialization to enable all features.")