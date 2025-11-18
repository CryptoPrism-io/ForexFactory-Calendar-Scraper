#!/usr/bin/env python3
"""
Configuration management for ForexFactory pipeline
Loads settings from environment variables and config files
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _mask_value(value):
    """Return a lightly masked representation of a credential"""
    if not value:
        return "***"
    if len(value) <= 2:
        return f"{value[0]}*" if len(value) == 2 else "*"
    return f"{value[0]}***{value[-1]}"


def mask_host(host):
    """Mask the final segment of an IP/domain so logs don't reveal the exact target"""
    if not host:
        return "***"
    parts = host.split('.')
    if len(parts) == 4 and all(part.isdigit() for part in parts if part):
        parts[-1] = "***"
        return '.'.join(parts)
    if len(parts) > 1:
        parts[-1] = "***"
        return '.'.join(parts)
    if len(host) <= 4:
        return host[0] + "**"
    return f"{host[:2]}***{host[-1:]}"


def describe_db_target(host, port, database, user=None):
    """Generate a masked DSN string suitable for logging"""
    masked_host = mask_host(host)
    user_part = f"{_mask_value(user)}@" if user else ""
    return f"{user_part}{masked_host}:{port}/{database}"


class Config:
    """Configuration manager for ForexFactory pipeline"""

    def __init__(self, env_file=None):
        """Initialize configuration from environment"""
        # Load .env file if provided
        if env_file and Path(env_file).exists():
            load_dotenv(env_file)
            logger.info(f"Loaded environment from: {env_file}")

        # Database Configuration
        self.POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
        self.POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
        self.POSTGRES_DB = os.getenv('POSTGRES_DB', 'forexfactory')
        self.POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
        self.POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')
        self.POSTGRES_POOL_SIZE = int(os.getenv('POSTGRES_POOL_SIZE', 5))

        # Scraper Configuration
        self.SCRAPER_TIMEOUT = int(os.getenv('SCRAPER_TIMEOUT', 30))
        self.SCRAPER_RETRIES = int(os.getenv('SCRAPER_RETRIES', 3))
        self.SCRAPER_VERBOSE = os.getenv('SCRAPER_VERBOSE', 'true').lower() == 'true'

        # Output Configuration
        self.OUTPUT_MODE = os.getenv('OUTPUT_MODE', 'both')  # 'csv', 'db', or 'both'
        self.CSV_OUTPUT_DIR = os.getenv('CSV_OUTPUT_DIR', 'csv_output')

        # Logging Configuration
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE = os.getenv('LOG_FILE', 'forexfactory.log')

    def get_db_config(self):
        """Get database configuration dict"""
        return {
            'host': self.POSTGRES_HOST,
            'port': self.POSTGRES_PORT,
            'database': self.POSTGRES_DB,
            'user': self.POSTGRES_USER,
            'password': self.POSTGRES_PASSWORD,
            'pool_size': self.POSTGRES_POOL_SIZE
        }

    def get_scraper_config(self):
        """Get scraper configuration dict"""
        return {
            'timeout': self.SCRAPER_TIMEOUT,
            'retries': self.SCRAPER_RETRIES,
            'verbose': self.SCRAPER_VERBOSE
        }

    def validate(self):
        """Validate critical configuration"""
        errors = []

        # Check database credentials
        if not self.POSTGRES_PASSWORD:
            errors.append("POSTGRES_PASSWORD is not set")

        if errors:
            logger.error("Configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False

        return True

    def __repr__(self):
        """String representation of configuration"""
        return f"""
ForexFactory Configuration:
  Database: {self.describe_db()}
  Output Mode: {self.OUTPUT_MODE}
  CSV Output Dir: {self.CSV_OUTPUT_DIR}
  Log Level: {self.LOG_LEVEL}
  Scraper Verbose: {self.SCRAPER_VERBOSE}
        """

    def describe_db(self):
        """Return masked connection description for safe logging"""
        return describe_db_target(
            self.POSTGRES_HOST,
            self.POSTGRES_PORT,
            self.POSTGRES_DB,
            self.POSTGRES_USER
        )


def get_config(env_file=None):
    """Factory function to get configuration instance"""
    if env_file is None:
        # Try to find .env in common locations
        possible_paths = [
            Path.cwd() / '.env',
            Path(__file__).parent.parent / '.env',
            Path(__file__).parent.parent.parent / '.env'
        ]
        for path in possible_paths:
            if path.exists():
                env_file = str(path)
                break

    config = Config(env_file)

    if not config.validate():
        logger.warning("Configuration validation failed, using defaults")

    return config
