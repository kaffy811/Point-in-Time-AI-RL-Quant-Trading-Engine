"""Bootstrap CLI: validates config, never fabricates research results."""
import argparse
import json
import logging

from src.utils.config import load_config
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    configure_logging()
    config = load_config(args.config)
    logging.getLogger("quant_engine").info("Phase 1 configuration validated")
    print(json.dumps({"config_hash": config.config_hash(), "status": "configuration_valid",
                      "research_results": "[TODO: 待实验结果]"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
