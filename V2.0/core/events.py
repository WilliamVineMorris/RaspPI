"""
Event Bus System for Scanner Module Communication

Provides a centralized event bus for inter-module communication.
This allows modules to communicate without tight coupling and
enables flexible event-driven architecture.

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .exceptions import ScannerSystemError

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScannerEvent:
    """Scanner system event data structure"""
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    source_module: str = "unknown"
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time() * 1000000)}")
    
    def __str__(self):
        return f"Event({self.event_type}, {self.source_module}, {self.priority.name})"


class EventConstants:
    """Predefined event types for scanner system"""
    
    # System Events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_READY = "system.ready"
    
    # Motion Events
    MOTION_STARTED = "motion.started"
    MOTION_COMPLETED = "motion.completed"
    MOTION_FAILED = "motion.failed"
    POSITION_REACHED = "motion.position_reached"
    MOTION_STOPPED = "motion.stopped"
    MOTION_HOME_COMPLETE = "motion.home_complete"
    MOTION_LIMITS_HIT = "motion.limits_hit"
    
    # Camera Events
    CAMERAS_READY = "camera.ready"
    CAMERAS_FAILED = "camera.failed"
    PHOTO_CAPTURED = "camera.photo_captured"
    PHOTO_FAILED = "camera.photo_failed"
    STREAMING_STARTED = "camera.streaming_started"
    STREAMING_STOPPED = "camera.streaming_stopped"
    CAMERA_SYNC_LOST = "camera.sync_lost"
    
    # LED Events
    LED_READY = "led.ready"
    LED_FAILED = "led.failed"
    FLASH_TRIGGERED = "led.flash_triggered"
    FLASH_COMPLETE = "led.flash_complete"
    LED_SAFETY_VIOLATION = "led.safety_violation"
    
    # Scan Events
    SCAN_STARTED = "scan.started"
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED = "scan.failed"
    SCAN_PAUSED = "scan.paused"
    SCAN_RESUMED = "scan.resumed"
    SCAN_POSITION_COMPLETE = "scan.position_complete"
    
    # Emergency Events
    EMERGENCY_STOP = "emergency.stop"
    SAFETY_VIOLATION = "safety.violation"
    HARDWARE_FAULT = "hardware.fault"
    
    # Web Interface Events
    WEB_CLIENT_CONNECTED = "web.client_connected"
    WEB_CLIENT_DISCONNECTED = "web.client_disconnected"
    WEB_COMMAND_RECEIVED = "web.command_received"
    
    # Data Events
    DATA_SAVED = "data.saved"
    DATA_TRANSFER_STARTED = "data.transfer_started"
    DATA_TRANSFER_COMPLETE = "data.transfer_complete"
    METADATA_GENERATED = "data.metadata_generated"


class EventSubscription:
    """Represents an event subscription"""
    
    def __init__(self, event_type: str, callback: Callable, subscriber_name: str = "unknown"):
        self.event_type = event_type
        self.callback = callback
        self.subscriber_name = subscriber_name
        self.subscription_time = datetime.now()
        self.call_count = 0
        self.last_called: Optional[datetime] = None
        self.active = True
    
    def __str__(self):
        return f"Subscription({self.event_type}, {self.subscriber_name})"


class EventBus:
    """
    Central event bus for scanner system module communication
    
    Features:
    - Thread-safe event publishing and subscription
    - Priority-based event handling
    - Event history and statistics
    - Async and sync callback support
    - Error isolation between subscribers
    """
    
    def __init__(self, max_history: int = 1000, enable_stats: bool = True):
        self._subscriptions: Dict[str, List[EventSubscription]] = {}
        self._event_history: List[ScannerEvent] = []
        self._max_history = max_history
        self._enable_stats = enable_stats
        self._lock = threading.RLock()
        self._stats = {
            'events_published': 0,
            'events_processed': 0,
            'subscription_count': 0,
            'error_count': 0
        }
        self._running = False
        
        logger.info("Event bus initialized")
    
    def subscribe(self, event_type: str, callback: Callable, subscriber_name: str = "unknown") -> bool:
        """
        Subscribe to an event type
        
        Args:
            event_type: Type of event to subscribe to (use EventConstants)
            callback: Function to call when event occurs
            subscriber_name: Name of subscribing module for debugging
            
        Returns:
            True if subscription successful
        """
        try:
            with self._lock:
                if event_type not in self._subscriptions:
                    self._subscriptions[event_type] = []
                
                subscription = EventSubscription(event_type, callback, subscriber_name)
                self._subscriptions[event_type].append(subscription)
                
                if self._enable_stats:
                    self._stats['subscription_count'] += 1
                
                logger.debug(f"Subscribed {subscriber_name} to {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to subscribe {subscriber_name} to {event_type}: {e}")
            return False
    
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event type
        
        Args:
            event_type: Type of event to unsubscribe from
            callback: The callback function to remove
            
        Returns:
            True if unsubscription successful
        """
        try:
            with self._lock:
                if event_type in self._subscriptions:
                    self._subscriptions[event_type] = [
                        sub for sub in self._subscriptions[event_type] 
                        if sub.callback != callback
                    ]
                    
                    if not self._subscriptions[event_type]:
                        del self._subscriptions[event_type]
                    
                    logger.debug(f"Unsubscribed from {event_type}")
                    return True
                
                return False  # Event type not found
                    
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {event_type}: {e}")
            return False
    
    def publish(self, event_type: str, data: Optional[Dict[str, Any]] = None, 
                source_module: str = "unknown", priority: EventPriority = EventPriority.NORMAL) -> bool:
        """
        Publish an event to all subscribers
        
        Args:
            event_type: Type of event (use EventConstants)
            data: Event data dictionary
            source_module: Module that published the event
            priority: Event priority level
            
        Returns:
            True if event published successfully
        """
        try:
            # Create event
            event = ScannerEvent(
                event_type=event_type,
                data=data or {},
                source_module=source_module,
                priority=priority
            )
            
            # Add to history
            with self._lock:
                self._event_history.append(event)
                if len(self._event_history) > self._max_history:
                    self._event_history.pop(0)
                
                if self._enable_stats:
                    self._stats['events_published'] += 1
            
            # Notify subscribers
            self._notify_subscribers(event)
            
            logger.debug(f"Published event: {event}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            with self._lock:
                if self._enable_stats:
                    self._stats['error_count'] += 1
            return False
    
    def _notify_subscribers(self, event: ScannerEvent):
        """Notify all subscribers of an event"""
        with self._lock:
            subscribers = self._subscriptions.get(event.event_type, [])
            active_subscribers = [sub for sub in subscribers if sub.active]
        
        for subscription in active_subscribers:
            self._call_subscriber(subscription, event)
    
    def _call_subscriber(self, subscription: EventSubscription, event: ScannerEvent):
        """Call a single subscriber with error isolation"""
        try:
            # Update subscription stats
            subscription.call_count += 1
            subscription.last_called = datetime.now()
            
            # Call the callback
            if asyncio.iscoroutinefunction(subscription.callback):
                # Handle async callbacks
                asyncio.create_task(subscription.callback(event))
            else:
                # Handle sync callbacks
                subscription.callback(event)
            
            if self._enable_stats:
                with self._lock:
                    self._stats['events_processed'] += 1
                    
        except Exception as e:
            logger.error(f"Error calling subscriber {subscription.subscriber_name} "
                        f"for event {event.event_type}: {e}")
            
            # Consider deactivating problematic subscribers
            if hasattr(e, '__class__') and 'CriticalError' in e.__class__.__name__:
                subscription.active = False
                logger.warning(f"Deactivated subscription {subscription} due to critical error")
            
            with self._lock:
                if self._enable_stats:
                    self._stats['error_count'] += 1
    
    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[ScannerEvent]:
        """
        Get recent event history
        
        Args:
            event_type: Filter by event type (None for all events)
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        with self._lock:
            history = self._event_history.copy()
        
        if event_type:
            history = [event for event in history if event.event_type == event_type]
        
        return history[-limit:] if limit else history
    
    def get_subscriptions(self) -> Dict[str, List[str]]:
        """Get current subscription information"""
        with self._lock:
            return {
                event_type: [sub.subscriber_name for sub in subscriptions]
                for event_type, subscriptions in self._subscriptions.items()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        with self._lock:
            stats = self._stats.copy()
            stats['active_subscriptions'] = sum(
                len(subs) for subs in self._subscriptions.values()
            )
            stats['event_types'] = len(self._subscriptions)
            stats['history_size'] = len(self._event_history)
        
        return stats
    
    def clear_history(self):
        """Clear event history"""
        with self._lock:
            self._event_history.clear()
            logger.info("Event history cleared")
    
    def shutdown(self):
        """Shutdown the event bus"""
        logger.info("Shutting down event bus")
        with self._lock:
            self._subscriptions.clear()
            self._event_history.clear()
            self._running = False


# Global event bus instance (can be imported by modules)
global_event_bus = EventBus()


# Convenience functions for common operations
def publish_system_event(event_type: str, data: Optional[Dict[str, Any]] = None, 
                        source_module: str = "system") -> bool:
    """Publish a system-level event"""
    return global_event_bus.publish(event_type, data, source_module, EventPriority.HIGH)


def publish_emergency_event(event_type: str, data: Optional[Dict[str, Any]] = None,
                          source_module: str = "unknown") -> bool:
    """Publish an emergency event with critical priority"""
    return global_event_bus.publish(event_type, data, source_module, EventPriority.CRITICAL)


def subscribe_to_system_events(callback: Callable, subscriber_name: str = "unknown") -> bool:
    """Subscribe to all system events"""
    system_events = [
        EventConstants.SYSTEM_STARTUP,
        EventConstants.SYSTEM_SHUTDOWN,
        EventConstants.SYSTEM_ERROR,
        EventConstants.EMERGENCY_STOP
    ]
    
    success = True
    for event_type in system_events:
        if not global_event_bus.subscribe(event_type, callback, subscriber_name):
            success = False
    
    return success