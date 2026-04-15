"""CLI for Yanantin database infrastructure.

Usage: uv run python -m yanantin.infra [command]

Default behavior: check if config exists, setup if not.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

from yanantin.infra.config import ApachetaDBConfig
from yanantin.infra.orchestrator import ApachetaDBSetup


def cmd_setup(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.setup():
        print("Setup complete.")
    else:
        print("Setup failed.", file=sys.stderr)
        sys.exit(1)


def cmd_check(args: argparse.Namespace) -> None:
    if not ApachetaDBConfig.default_config_file.exists():
        print("No config found. Run: uv run python -m yanantin.infra setup")
        sys.exit(1)
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.check():
        print("All checks passed.")
    else:
        print("Check failed.", file=sys.stderr)
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    setup.start()
    print(f"Started {config.db.get('container', 'remote instance')}.")


def cmd_stop(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    setup.stop()
    print(f"Stopped {config.db.get('container', 'remote instance')}.")


def cmd_status(args: argparse.Namespace) -> None:
    if not ApachetaDBConfig.default_config_file.exists():
        print("No config found. Run: uv run python -m yanantin.infra setup")
        return
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    info = setup.status()
    for k, v in info.items():
        print(f"  {k}: {v}")


def cmd_reset(args: argparse.Namespace) -> None:
    confirm = input("This will DELETE all data. Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.reset():
        print("Reset complete.")
    else:
        print("Reset failed.", file=sys.stderr)
        sys.exit(1)


def cmd_connect(args: argparse.Namespace) -> None:
    password = args.admin_password
    if not password:
        password = getpass.getpass("Admin password for remote instance: ")

    ApachetaDBConfig._instance = None
    config = ApachetaDBConfig(
        host=args.host,
        port=args.port,
        ssl=args.ssl,
        admin_password=password,
        docker_managed=False,
    )
    setup = ApachetaDBSetup(config)
    if setup.setup():
        print("Remote connection configured.")
    else:
        print("Setup failed.", file=sys.stderr)
        sys.exit(1)


def cmd_default(args: argparse.Namespace) -> None:
    if ApachetaDBConfig.default_config_file.exists():
        cmd_check(args)
    else:
        cmd_setup(args)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Yanantin database infrastructure",
        prog="python -m yanantin.infra",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.set_defaults(func=cmd_default)

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Stand up ArangoDB from nothing").set_defaults(func=cmd_setup)
    sub.add_parser("check", help="Verify everything is working").set_defaults(func=cmd_check)
    sub.add_parser("start", help="Start the container").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="Stop the container").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="Show container and database state").set_defaults(func=cmd_status)

    reset_p = sub.add_parser("reset", help="Wipe and recreate")
    reset_p.add_argument("--rebuild", action="store_true")
    reset_p.set_defaults(func=cmd_reset)

    connect_p = sub.add_parser("connect", help="Configure for remote instance")
    connect_p.add_argument("--host", required=True)
    connect_p.add_argument("--port", type=int, default=8529)
    connect_p.add_argument("--ssl", action="store_true")
    connect_p.add_argument("--admin-password", default=None)
    connect_p.set_defaults(func=cmd_connect)

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    args.func(args)


if __name__ == "__main__":
    main()
