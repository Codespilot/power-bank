#!/usr/bin/env python
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if os.getenv("MYSQL_DRIVER", None) == "pymysql":
    import pymysql
    import pymysql.cursors
    import pymysql.connections
    pymysql.install_as_MySQLdb()


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Is it installed and available on your PYTHONPATH?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
