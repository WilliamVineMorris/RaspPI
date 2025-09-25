#!/usr/bin/env python3
"""
Quick Fix for Homing Detection
Replace the home_axes method in simplified_fluidnc_controller_fixed.py
"""

import asyncio
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def create_enhanced_home_axes_method():
    """
    Returns enhanced home_axes method that detects [MSG:DBG: Homing done]
    Based on your FluidNC message capture
    """
    
    async def home_axes(self, axes: Optional[list] = None) -> bool:
        """Enhanced homing with FluidNC debug message detection"""
        try:
            logger.info("🏠 Starting ENHANCED homing with debug message detection")
            
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
            success, response = await self._send_command(homing_command)
            
            if not success:
                logger.error(f"❌ Homing command failed: {response}")
                return False
            
            logger.info(f"🏠 Command sent successfully: {response}")
            
            # Enhanced monitoring for FluidNC debug messages
            homing_timeout = 45.0  # Increased from 30s based on actual 22s timing
            start_time = time.time()
            
            homing_done_detected = False
            axes_homed = set()
            last_status_check = 0
            
            logger.info("🏠 Monitoring for '[MSG:DBG: Homing done]' message...")
            
            while time.time() - start_time < homing_timeout:
                elapsed = time.time() - start_time
                
                # Check recent protocol messages for debug completion signal
                if hasattr(self.protocol, 'get_recent_raw_messages'):
                    recent_messages = self.protocol.get_recent_raw_messages(30)
                    
                    for message in recent_messages:
                        # Primary completion detection - exactly like your logs
                        if "[MSG:DBG: Homing done]" in message:
                            logger.info("🎯 DETECTED: [MSG:DBG: Homing done] - Perfect completion signal!")
                            homing_done_detected = True
                            break
                        
                        # Individual axis completion 
                        if "[MSG:Homed:" in message:
                            try:
                                axis = message.split("[MSG:Homed:")[1].split("]")[0]
                                if axis not in axes_homed:
                                    axes_homed.add(axis)
                                    logger.info(f"✅ DETECTED: Axis {axis} homed")
                            except:
                                pass
                        
                        # Error detection
                        if any(error in message.lower() for error in ['alarm', 'error']):
                            logger.error(f"❌ DETECTED: Homing error - {message}")
                            return False
                
                # Break if we found the completion signal
                if homing_done_detected:
                    logger.info(f"✅ Homing completed via debug message after {elapsed:.1f}s")
                    break
                
                # Fallback: status monitoring every 2 seconds
                if elapsed - last_status_check >= 2.0:
                    status = self.protocol.get_current_status()
                    last_status_check = elapsed
                    
                    if status and status.state:
                        state_lower = status.state.lower()
                        logger.debug(f"🏠 Status at {elapsed:.1f}s: {status.state}")
                        
                        # Enhanced fallback: Idle + time-based completion
                        if state_lower in ['idle', 'run'] and elapsed > 20.0:
                            logger.info(f"✅ Fallback detection: {status.state} after {elapsed:.1f}s (likely completed)")
                            homing_done_detected = True
                            break
                        elif state_lower in ['alarm', 'error']:
                            logger.error(f"❌ Status failure: {status.state}")
                            return False
                
                await asyncio.sleep(0.2)  # Check every 200ms
            
            # Timeout check
            if not homing_done_detected:
                logger.error(f"❌ Homing timeout after {homing_timeout}s - No completion signal detected")
                logger.info("💡 If homing actually completed, check protocol message capture")
                return False
            
            # Final verification and position update
            await asyncio.sleep(1.0)  # Let system settle
            final_status = self.protocol.get_current_status()
            
            if final_status and final_status.state.lower() in ['idle', 'run']:
                logger.info(f"✅ Final verification: {final_status.state}")
            else:
                logger.warning(f"⚠️ Final state unexpected: {final_status.state if final_status else 'None'}")
            
            # Update position after homing
            await self._update_current_position()
            
            # Emit enhanced completion event
            self._emit_event("homing_completed", {
                "axes": axes or ['x', 'y', 'z', 'c'],
                "final_position": self.current_position.to_dict(),
                "axes_homed": list(axes_homed),
                "completion_time": elapsed,
                "detection_method": "debug_message_enhanced"
            })
            
            logger.info(f"✅ ENHANCED homing completed successfully!")
            logger.info(f"📊 Duration: {elapsed:.1f}s, Axes detected: {axes_homed}")
            logger.info(f"📍 Final position: {self.current_position}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced homing failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    return home_axes

# Usage instructions:
"""
To apply this fix:

1. This method needs to replace the existing home_axes method in 
   simplified_fluidnc_controller_fixed.py

2. The key improvement is looking for the exact message from your logs:
   [MSG:DBG: Homing done]

3. This should be MUCH more reliable than status-only detection!

Your logs show the perfect completion sequence:
   [22:44:31.124] RECEIVED: [MSG:DBG: Homing done]  ← This is the golden signal!
   [22:44:31.257] RECEIVED: <Idle|MPos:0.000,200.000,37.333,-5.000,0.000,0.000|...>

The enhanced protocol now captures all raw messages, so this detection should work perfectly.
"""