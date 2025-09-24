#!/usr/bin/env python3
"""
Fixed web interface startup with better Gunicorn configuration and fallback options
"""

import argparse
import sys
import os

def start_web_interface_fixed():
    """Start web interface with improved configuration"""
    
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from scanning.scan_orchestrator import ScanOrchestrator
    from web.web_interface import ScannerWebInterface
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(description='Scanner Web Interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--mode', choices=['development', 'production'], default='development', 
                       help='Server mode')
    parser.add_argument('--force-flask', action='store_true', 
                       help='Force Flask dev server even in production mode')
    
    args = parser.parse_args()
    
    try:
        logger.info("🚀 Initializing Scanner System...")
        
        # Initialize config manager first
        from core.config_manager import ConfigManager
        from pathlib import Path
        
        # Use the existing scanner config
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        
        if not config_file.exists():
            logger.error(f"❌ Configuration file not found: {config_file}")
            logger.info("💡 Make sure you're running from the V2.0 directory")
            sys.exit(1)
        
        config_manager = ConfigManager(str(config_file))
        logger.info("✅ Config manager initialized")
        
        # Initialize orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize all hardware connections
        logger.info("🔌 Initializing hardware connections...")
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orchestrator.initialize())
            logger.info("✅ Orchestrator and hardware initialized")
        except Exception as e:
            logger.error(f"❌ Hardware initialization failed: {e}")
            logger.info("🔧 Some hardware may not be available - continuing with available components")
        finally:
            # Don't close the loop - web interface needs it
            pass
        
        # Initialize web interface
        web_interface = ScannerWebInterface(orchestrator)
        logger.info("✅ Web interface initialized")
        
        # Determine server mode
        use_production = (args.mode == 'production' and not args.force_flask)
        
        if use_production:
            logger.info("🏭 Starting in production mode with optimized Gunicorn")
        else:
            logger.info("🔧 Starting in development mode with Flask dev server")
        
        logger.info(f"🌐 Access the interface at: http://{args.host}:{args.port}")
        logger.info("📱 Mobile-friendly interface available")
        logger.info("🛑 Press Ctrl+C to stop")
        
        # Start the web server with improved configuration
        start_server_improved(web_interface, args.host, args.port, use_production, args.force_flask)
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Failed to start web interface: {e}")
        sys.exit(1)

def start_server_improved(web_interface, host, port, use_production, force_flask):
    """Start server with improved configuration"""
    
    if use_production and not force_flask:
        # Try production server with Pi-optimized settings
        try:
            start_gunicorn_optimized(web_interface, host, port)
        except ImportError:
            web_interface.logger.warning("Gunicorn not available, falling back to Flask")
            start_flask_server(web_interface, host, port)
        except Exception as e:
            web_interface.logger.error(f"Gunicorn failed: {e}, falling back to Flask")
            start_flask_server(web_interface, host, port)
    else:
        # Use Flask development server
        start_flask_server(web_interface, host, port)

def start_gunicorn_optimized(web_interface, host, port):
    """Start Gunicorn with Pi-optimized settings"""
    from gunicorn.app.base import BaseApplication
    
    class OptimizedApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()
        
        def load_config(self):
            config = {key: value for key, value in self.options.items()
                     if key in self.cfg.settings and value is not None}
            for key, value in config.items():
                self.cfg.set(key.lower(), value)
        
        def load(self):
            return self.application
    
    # Pi-optimized Gunicorn configuration
    options = {
        'bind': f'{host}:{port}',
        'workers': 2,  # Reduced for Pi hardware
        'worker_class': 'sync',  # Simple sync workers
        'worker_connections': 100,  # Reduced connections
        'max_requests': 500,  # Lower to prevent memory issues
        'max_requests_jitter': 25,
        'timeout': 60,  # Longer timeout for Pi
        'keepalive': 5,
        'preload_app': False,  # Disable preload to reduce memory
        'access_logfile': '-',
        'error_logfile': '-',
        'log_level': 'info',
        'capture_output': True
    }
    
    web_interface.logger.info("🏭 Starting optimized Gunicorn server for Raspberry Pi")
    web_interface._running = True
    web_interface._start_status_updater()
    
    OptimizedApplication(web_interface.app, options).run()

def start_flask_server(web_interface, host, port):
    """Start Flask development server"""
    web_interface.logger.info("🔧 Starting Flask development server")
    web_interface._running = True
    web_interface._start_status_updater()
    
    web_interface.app.run(
        host=host, 
        port=port, 
        debug=False,  # Disable debug for stability
        use_reloader=False,  # Disable reloader
        threaded=True  # Enable threading
    )

if __name__ == "__main__":
    start_web_interface_fixed()