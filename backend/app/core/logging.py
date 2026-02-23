import logging
import sys
import os
import json
from datetime import datetime
from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "props"):
            log_record.update(record.props)
            
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)


def setup_logging():
    """Configure logging with both file and console output"""
    
    # Create log directory in /tmp (always writable)
    log_dir = '/tmp/logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Get log level
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    
    # Create handlers
    file_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'))
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JSONFormatter())
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Configure the logger that will be used by the app
    logger = logging.getLogger("app")
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    
    # Configure root logger for other modules
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # Set external loggers to warning
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Test write
    logger.info(f"Logging system initialized. Log file: {os.path.join(log_dir, 'app.log')}")
    
    return logger


# Create and configure logger on import
logger = setup_logging()