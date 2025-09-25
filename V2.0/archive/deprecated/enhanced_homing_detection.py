#!/usr/bin/env python3
"""
Enhanced Homing Detection Implementation
Based on FluidNC message capture analysis
"""

import asyncio
import time
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)

async def enhanced_home_axes(controller, axes: Optional[list] = None) -> bool:
    """
    Enhanced homing with FluidNC debug message detection
    
    Key detection signals from your capture:
    - [MSG:DBG: Homing Cycle Y] - Homing starts
    - [MSG:Homed:Y] - Individual axis completion  
    - [MSG:DBG: Homing done] - Final completion signal
    - <Idle|...> - Final state confirmation
    """
    try:
        logger.info("🏠 Starting enhanced homing with debug message detection")
        
        # Determine homing command
        if axes is None or (isinstance(axes, list) and set([ax.upper() for ax in axes]) == {'X', 'Y', 'Z', 'C'}):
            homing_command = "$H"
            logger.info("🏠 Full homing sequence ($H)")
        else:
            axis_string = ''.join(axes).upper()
            homing_command = f"$H{axis_string}"
            logger.info(f"🏠 Selective homing ({homing_command})")
        
        # Send homing command
        logger.info(f"🏠 Sending: {homing_command}")
        success, response = await controller._send_command(homing_command)
        
        if not success:
            logger.error(f"❌ Homing command failed: {response}")
            return False
        
        logger.info(f"🏠 Command sent successfully: {response}")
        
        # Enhanced monitoring based on your FluidNC message patterns
        homing_timeout = 45.0  # Based on your 22-second actual time + buffer
        start_time = time.time()
        
        # Detection variables
        homing_done_detected = False
        axes_homed: Set[str] = set()
        last_status_check = 0
        
        logger.info("🏠 Monitoring for FluidNC debug messages...")
        logger.info("🎯 Looking for: [MSG:DBG: Homing done] and [MSG:Homed:X/Y]")
        
        while time.time() - start_time < homing_timeout:
            elapsed = time.time() - start_time
            
            # Method 1: Check for debug messages in recent protocol activity
            # This is a placeholder - we need to enhance the protocol to capture debug messages
            if hasattr(controller.protocol, 'get_recent_raw_messages'):
                recent_messages = controller.protocol.get_recent_raw_messages()
                
                for message in recent_messages:
                    # Primary completion detection
                    if "[MSG:DBG: Homing done]" in message:
                        logger.info("🎯 DETECTED: [MSG:DBG: Homing done]")
                        homing_done_detected = True
                        break
                    
                    # Individual axis completion detection
                    if "[MSG:Homed:" in message:
                        try:
                            axis = message.split("[MSG:Homed:")[1].split("]")[0]
                            if axis not in axes_homed:
                                axes_homed.add(axis)
                                logger.info(f"✅ DETECTED: Axis {axis} homed")
                        except:
                            pass
                    
                    # Error detection
                    if any(error_word in message.lower() for error_word in ['alarm', 'error', 'failed']):
                        logger.error(f"❌ DETECTED: Error in homing - {message}")
                        return False
            
            # Primary completion check
            if homing_done_detected:
                logger.info(f"✅ Homing completed via debug message after {elapsed:.1f}s")
                break
            
            # Method 2: Fallback status monitoring (every 2 seconds)
            if elapsed - last_status_check >= 2.0:
                status = controller.protocol.get_current_status()
                last_status_check = elapsed
                
                if status and status.state:
                    state_lower = status.state.lower()
                    logger.debug(f"🏠 Status at {elapsed:.1f}s: {status.state}")
                    
                    # Fallback: Idle state after reasonable time suggests completion
                    if state_lower in ['idle', 'run'] and elapsed > 15.0:
                        logger.info(f"✅ Fallback detection: {status.state} after {elapsed:.1f}s")
                        homing_done_detected = True
                        break
                    elif state_lower in ['alarm', 'error']:
                        logger.error(f"❌ Status indicates failure: {status.state}")
                        return False
            
            await asyncio.sleep(0.2)  # Brief pause
        
        # Timeout check
        if not homing_done_detected:
            logger.error(f"❌ Homing timeout after {homing_timeout}s")
            return False
        
        # Final verification
        await asyncio.sleep(1.0)  # Allow system to settle
        final_status = controller.protocol.get_current_status()
        
        if final_status and final_status.state.lower() in ['idle', 'run']:
            logger.info(f"✅ Final verification: {final_status.state}")
        else:
            logger.warning(f"⚠️ Unexpected final state: {final_status.state if final_status else 'None'}")
        
        # Update position
        await controller._update_current_position()
        
        # Emit completion event
        controller._emit_event("homing_completed", {
            "axes": axes or ['x', 'y', 'z', 'c'],
            "final_position": controller.current_position.to_dict(),
            "axes_homed": list(axes_homed),
            "completion_time": elapsed,
            "detection_method": "debug_message" if homing_done_detected else "status_fallback"
        })
        
        logger.info(f"✅ Enhanced homing completed successfully!")
        logger.info(f"📊 Time: {elapsed:.1f}s, Axes: {axes_homed}")
        logger.info(f"📍 Position: {controller.current_position}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Enhanced homing failed: {e}")
        controller.stats['errors_encountered'] += 1
        return False

# Integration instructions:
"""
To integrate this enhanced homing detection:

1. Replace the home_axes method in simplified_fluidnc_controller_fixed.py
2. Add message capture capability to the protocol
3. The key improvement is detecting [MSG:DBG: Homing done] instead of just status changes

Your FluidNC logs show the perfect completion signal:
[22:44:31.124] RECEIVED: [MSG:DBG: Homing done]
[22:44:31.257] RECEIVED: <Idle|MPos:0.000,200.000,37.333,-5.000,0.000,0.000|...>

This approach will be much more reliable than the current status-only detection!
"""