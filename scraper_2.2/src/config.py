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
  Database: {self.POSTGRES_USER}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}
  Output Mode: {self.OUTPUT_MODE}
  CSV Output Dir: {self.CSV_OUTPUT_DIR}
  Log Level: {self.LOG_LEVEL}
  Scraper Verbose: {self.SCRAPER_VERBOSE}
        """


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
