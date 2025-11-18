#!/usr/bin/env python3
"""
Migration runner for ForexFactory database schema
Applies SQL migration files to PostgreSQL database
"""

import os
import sys
import logging
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Add src to path for shared config helpers
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from config import describe_db_target

# Load .env file
env_file = Path(__file__).parent.parent / '.env'
if env_file.exists():
    load_dotenv(env_file)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MigrationRunner:
    def __init__(self, host, port, database, user, password):
        """Initialize migration runner"""
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None

    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(
                f"Connected to database: "
                f"{describe_db_target(self.host, self.port, self.database, self.user)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")

    def execute_sql_file(self, sql_file_path):
        """Execute SQL file"""
        try:
            with open(sql_file_path, 'r') as f:
                sql = f.read()

            with self.conn.cursor() as cursor:
                cursor.execute(sql)
                self.conn.commit()

            logger.info(f"✓ Successfully executed: {Path(sql_file_path).name}")
            return True
        except Exception as e:
            logger.error(f"✗ Error executing {Path(sql_file_path).name}: {e}")
            self.conn.rollback()
            return False

    def run_migrations(self, migration_dir):
        """Run all migrations in order"""
        migration_files = sorted(Path(migration_dir).glob('*.sql'))

        if not migration_files:
            logger.warning("No migration files found")
            return False

        logger.info(f"Found {len(migration_files)} migration file(s)")

        for migration_file in migration_files:
            logger.info(f"\nRunning: {migration_file.name}")
            if not self.execute_sql_file(str(migration_file)):
                logger.error("Migration failed, aborting")
                return False

        logger.info("\n" + "="*60)
        logger.info("✓ All migrations completed successfully!")
        logger.info("="*60)
        return True


def main():
    """Main migration entry point"""
    # Load environment variables
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = int(os.getenv('POSTGRES_PORT', 5432))
    database = os.getenv('POSTGRES_DB', 'forexfactory')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'postgres')

    # Get migration directory
    migration_dir = Path(__file__).parent

    print("\n" + "="*60)
    print("FOREXFACTORY DATABASE MIGRATION RUNNER")
    print("="*60)
    print(f"Database: {describe_db_target(host, port, database, user)}")
    print(f"Migration Directory: {migration_dir}")
    print("="*60 + "\n")

    # Run migrations
    runner = MigrationRunner(host, port, database, user, password)

    if not runner.connect():
        print("✗ Failed to connect to database")
        return 1

    try:
        success = runner.run_migrations(migration_dir)
        return 0 if success else 1
    finally:
        runner.disconnect()


if __name__ == '__main__':
    exit(main())
