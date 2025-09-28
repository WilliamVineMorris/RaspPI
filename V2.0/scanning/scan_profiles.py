"""
Scan Profile Management System

Manages quality and speed profiles with customizable parameters for the scanner.
Provides both preset profiles and custom user-defined profiles with persistence.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class ProfileType(Enum):
    """Types of scan profiles"""
    QUALITY = "quality"
    SPEED = "speed"
    CUSTOM = "custom"
    COMBINED = "combined"

@dataclass
class QualityProfile:
    """Quality profile with camera and capture settings"""
    name: str
    description: str
    resolution: List[int]  # [width, height]
    jpeg_quality: int  # 0-100
    capture_timeout: float  # seconds
    iso_preference: str  # 'auto', 'low_noise', 'high_speed', 'lowest_iso'
    exposure_mode: str  # 'auto', 'manual', 'calibrated'
    exposure_time: Optional[int] = None  # microseconds if manual
    analogue_gain: Optional[float] = None  # if manual
    denoise_level: int = 0  # 0-10 post-processing denoise
    sharpening_level: int = 0  # 0-10 post-processing sharpening
    is_custom: bool = False
    is_editable: bool = True

@dataclass
class SpeedProfile:
    """Speed profile with motion control settings"""
    name: str
    description: str
    feedrate_multiplier: float  # 0.1 to 2.0
    settling_delay: float  # seconds to wait after movement
    acceleration_factor: float  # 0.5 to 1.5 (affects jerk/smoothness)
    motion_precision: str  # 'high', 'normal', 'fast'
    capture_delay: float  # delay between move complete and capture
    parallel_processing: bool  # enable parallel image processing
    skip_confirmations: bool  # skip non-critical confirmations
    is_custom: bool = False
    is_editable: bool = True

class ScanProfileManager:
    """Manages scan profiles with persistence and customization"""
    
    # Default quality profiles
    DEFAULT_QUALITY_PROFILES = {
        'low': QualityProfile(
            name='low',
            description='Draft Quality (Fast)',
            resolution=[1920, 1080],
            jpeg_quality=75,
            capture_timeout=1.0,
            iso_preference='auto',
            exposure_mode='auto',
            denoise_level=0,
            sharpening_level=0,
            is_editable=False
        ),
        'medium': QualityProfile(
            name='medium',
            description='Standard Quality',
            resolution=[3840, 2160],
            jpeg_quality=85,
            capture_timeout=2.0,
            iso_preference='low_noise',
            exposure_mode='auto',
            denoise_level=2,
            sharpening_level=2,
            is_editable=False
        ),
        'high': QualityProfile(
            name='high',
            description='High Quality (Detailed)',
            resolution=[4608, 2592],
            jpeg_quality=95,
            capture_timeout=3.0,
            iso_preference='low_noise',
            exposure_mode='calibrated',
            denoise_level=3,
            sharpening_level=3,
            is_editable=False
        ),
        'ultra': QualityProfile(
            name='ultra',
            description='Maximum Quality (Slow)',
            resolution=[4608, 2592],
            jpeg_quality=98,
            capture_timeout=5.0,
            iso_preference='lowest_iso',
            exposure_mode='calibrated',
            exposure_time=32000,
            analogue_gain=1.0,
            denoise_level=4,
            sharpening_level=2,
            is_editable=False
        )
    }
    
    # Default speed profiles
    DEFAULT_SPEED_PROFILES = {
        'slow': SpeedProfile(
            name='slow',
            description='Precision (Slowest)',
            feedrate_multiplier=0.6,
            settling_delay=3.0,
            acceleration_factor=0.8,
            motion_precision='high',
            capture_delay=0.5,
            parallel_processing=False,
            skip_confirmations=False,
            is_editable=False
        ),
        'medium': SpeedProfile(
            name='medium',
            description='Balanced',
            feedrate_multiplier=1.0,
            settling_delay=2.0,
            acceleration_factor=1.0,
            motion_precision='normal',
            capture_delay=0.2,
            parallel_processing=True,
            skip_confirmations=False,
            is_editable=False
        ),
        'fast': SpeedProfile(
            name='fast',
            description='Quick Scan (Fastest)',
            feedrate_multiplier=1.4,
            settling_delay=1.5,
            acceleration_factor=1.2,
            motion_precision='fast',
            capture_delay=0.1,
            parallel_processing=True,
            skip_confirmations=True,
            is_editable=False
        )
    }
    
    def __init__(self, profiles_directory: Optional[Path] = None):
        """Initialize profile manager
        
        Args:
            profiles_directory: Directory to store custom profiles
        """
        self.profiles_dir = profiles_directory or Path.home() / '.scanner_profiles'
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize with defaults
        self.quality_profiles = self.DEFAULT_QUALITY_PROFILES.copy()
        self.speed_profiles = self.DEFAULT_SPEED_PROFILES.copy()
        
        # Load custom profiles
        self._load_custom_profiles()
        
        logger.info(f"Profile manager initialized with {len(self.quality_profiles)} quality and {len(self.speed_profiles)} speed profiles")
    
    def _load_custom_profiles(self):
        """Load custom profiles from disk"""
        try:
            # Load quality profiles
            quality_file = self.profiles_dir / 'quality_profiles.json'
            if quality_file.exists():
                with open(quality_file, 'r') as f:
                    custom_quality = json.load(f)
                    for name, profile_data in custom_quality.items():
                        self.quality_profiles[name] = QualityProfile(**profile_data)
                        
            # Load speed profiles
            speed_file = self.profiles_dir / 'speed_profiles.json'
            if speed_file.exists():
                with open(speed_file, 'r') as f:
                    custom_speed = json.load(f)
                    for name, profile_data in custom_speed.items():
                        self.speed_profiles[name] = SpeedProfile(**profile_data)
                        
            logger.debug(f"Loaded {len(self.quality_profiles) - len(self.DEFAULT_QUALITY_PROFILES)} custom quality profiles")
            logger.debug(f"Loaded {len(self.speed_profiles) - len(self.DEFAULT_SPEED_PROFILES)} custom speed profiles")
            
        except Exception as e:
            logger.error(f"Failed to load custom profiles: {e}")
    
    def save_custom_profiles(self):
        """Save custom profiles to disk"""
        try:
            # Save only custom quality profiles
            custom_quality = {
                name: asdict(profile) 
                for name, profile in self.quality_profiles.items() 
                if profile.is_custom
            }
            if custom_quality:
                with open(self.profiles_dir / 'quality_profiles.json', 'w') as f:
                    json.dump(custom_quality, f, indent=2)
                    
            # Save only custom speed profiles
            custom_speed = {
                name: asdict(profile)
                for name, profile in self.speed_profiles.items()
                if profile.is_custom
            }
            if custom_speed:
                with open(self.profiles_dir / 'speed_profiles.json', 'w') as f:
                    json.dump(custom_speed, f, indent=2)
                    
            logger.info("Custom profiles saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save custom profiles: {e}")
    
    def get_quality_profile(self, name: str) -> Optional[QualityProfile]:
        """Get a quality profile by name"""
        return self.quality_profiles.get(name)
    
    def get_speed_profile(self, name: str) -> Optional[SpeedProfile]:
        """Get a speed profile by name"""
        return self.speed_profiles.get(name)
    
    def create_custom_quality_profile(self, base_profile: str, modifications: Dict[str, Any], 
                                     custom_name: str) -> QualityProfile:
        """Create a custom quality profile based on existing profile"""
        base = self.quality_profiles.get(base_profile)
        if not base:
            raise ValueError(f"Base profile '{base_profile}' not found")
            
        # Create new profile from base
        profile_data = asdict(base)
        profile_data.update(modifications)
        profile_data['name'] = custom_name
        profile_data['is_custom'] = True
        profile_data['is_editable'] = True
        
        custom_profile = QualityProfile(**profile_data)
        self.quality_profiles[custom_name] = custom_profile
        
        # Save to disk
        self.save_custom_profiles()
        
        logger.info(f"Created custom quality profile: {custom_name}")
        return custom_profile
    
    def create_custom_speed_profile(self, base_profile: str, modifications: Dict[str, Any],
                                   custom_name: str) -> SpeedProfile:
        """Create a custom speed profile based on existing profile"""
        base = self.speed_profiles.get(base_profile)
        if not base:
            raise ValueError(f"Base profile '{base_profile}' not found")
            
        # Create new profile from base
        profile_data = asdict(base)
        profile_data.update(modifications)
        profile_data['name'] = custom_name
        profile_data['is_custom'] = True
        profile_data['is_editable'] = True
        
        custom_profile = SpeedProfile(**profile_data)
        self.speed_profiles[custom_name] = custom_profile
        
        # Save to disk
        self.save_custom_profiles()
        
        logger.info(f"Created custom speed profile: {custom_name}")
        return custom_profile
    
    def update_profile(self, profile_type: ProfileType, name: str, 
                       modifications: Dict[str, Any]) -> bool:
        """Update an existing custom profile"""
        if profile_type == ProfileType.QUALITY:
            profile = self.quality_profiles.get(name)
            if profile and profile.is_editable:
                for key, value in modifications.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                self.save_custom_profiles()
                return True
                
        elif profile_type == ProfileType.SPEED:
            profile = self.speed_profiles.get(name)
            if profile and profile.is_editable:
                for key, value in modifications.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                self.save_custom_profiles()
                return True
                
        return False
    
    def delete_custom_profile(self, profile_type: ProfileType, name: str) -> bool:
        """Delete a custom profile"""
        if profile_type == ProfileType.QUALITY:
            if name in self.quality_profiles and self.quality_profiles[name].is_custom:
                del self.quality_profiles[name]
                self.save_custom_profiles()
                return True
                
        elif profile_type == ProfileType.SPEED:
            if name in self.speed_profiles and self.speed_profiles[name].is_custom:
                del self.speed_profiles[name]
                self.save_custom_profiles()
                return True
                
        return False
    
    def get_scan_settings(self, quality_name: str = 'medium', 
                         speed_name: str = 'medium') -> Dict[str, Any]:
        """Get combined scan settings from quality and speed profiles"""
        quality = self.quality_profiles.get(quality_name, self.DEFAULT_QUALITY_PROFILES['medium'])
        speed = self.speed_profiles.get(speed_name, self.DEFAULT_SPEED_PROFILES['medium'])
        
        return {
            'camera_settings': asdict(quality),
            'motion_settings': asdict(speed),
            'profile_names': {
                'quality': quality_name,
                'speed': speed_name
            }
        }