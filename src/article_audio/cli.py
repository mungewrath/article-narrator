from __future__ import annotations

import argparse

from article_audio.bridge import ArticleSqsBridge, configure_logging
from article_audio.config import BridgeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll SQS and durably hand off article jobs"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one message and exit",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = BridgeConfig.from_env()
    if args.once:
        config = BridgeConfig(
            queue_url=config.queue_url,
            jobs_root=config.jobs_root,
            region_name=config.region_name,
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            wait_time_seconds=config.wait_time_seconds,
            visibility_timeout=config.visibility_timeout,
            idle_sleep_seconds=config.idle_sleep_seconds,
            handoff_command=config.handoff_command,
            handoff_shell=config.handoff_shell,
            log_level=config.log_level,
            once=True,
        )

    configure_logging(config.log_level)
    ArticleSqsBridge(config).run_forever()


if __name__ == "__main__":
    main()
