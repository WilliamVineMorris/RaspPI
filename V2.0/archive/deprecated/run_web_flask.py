#!/usr/bin/env python3
"""
Simplified Flask-only web interface launcher - no Gunicorn complexity
"""

import argparse
import sys
import os
import signal
import logging
import asyncio

def start_web_interface_flask():
    """Start web interface with Flask only - simplified and reliable"""
    
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from scanning.scan_orchestrator import ScanOrchestrator
    from web.web_interface import ScannerWebInterface
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(description='Scanner Web Interface (Flask Only)')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Global shutdown handler
    orchestrator = None
    web_interface = None
    
    def signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        if web_interface:
            web_interface._running = False
        if orchestrator:
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(orchestrator.shutdown())
            except:
                pass
        logger.info("✅ Graceful shutdown complete")
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("🚀 Initializing Scanner System (Flask Mode)...")
        
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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orchestrator.initialize())
            logger.info("✅ Orchestrator and hardware initialized")
        except Exception as e:
            logger.error(f"❌ Hardware initialization failed: {e}")
            logger.info("🔧 Some hardware may not be available - continuing with available components")
        
        # Initialize web interface
        web_interface = ScannerWebInterface(orchestrator)
        logger.info("✅ Web interface initialized")
        
        # Flask configuration info
        logger.info("🌐 Starting Flask web server (no Gunicorn complexity)")
        logger.info(f"🔗 Access the interface at: http://{args.host}:{args.port}")
        logger.info("📱 Mobile-friendly interface available")
        logger.info("🎥 Both camera streams supported")
        logger.info("🛑 Press Ctrl+C to stop")
        
        # Start Flask server
        web_interface.start_web_server(
            host=args.host, 
            port=args.port, 
            debug=args.debug, 
            production=not args.debug
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Failed to start web interface: {e}")
        import traceback
        logger.error(f"Full error: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    start_web_interface_flask()