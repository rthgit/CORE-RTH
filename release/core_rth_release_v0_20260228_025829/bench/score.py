import argparse
from pathlib import Path

import runner


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark scoring helper")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", help="Path to a single run directory")
    group.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"), help="Compare two run directories")
    args = parser.parse_args()

    if args.run:
        payload = runner.score_run(Path(args.run), write_outputs=True)
        runner.print_run_summary(payload)
        return

    run_a, run_b = args.compare
    payload = runner.compare_runs(Path(run_a), Path(run_b))
    runner.print_compare_summary(payload)


if __name__ == "__main__":
    main()

