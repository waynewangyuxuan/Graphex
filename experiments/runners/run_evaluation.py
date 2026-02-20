"""Evaluate experiment output against ground truth.

Usage:
    python experiments/runners/run_evaluation.py \\
        experiments/results/v5-flash-lite/threads-cv_output.json \\
        benchmark/datasets/papers/threads-cv/ground_truth.json
"""

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.evaluation.evaluator import evaluate_against_ground_truth


def run(output_path: str, gt_path: str) -> None:
    with open(output_path) as f:
        extracted = json.load(f)

    evaluation = evaluate_against_ground_truth(extracted, Path(gt_path))

    print(f"\n{'='*40}")
    print("NODE RECALL")
    n = evaluation["nodes"]
    print(f"  All:  {n['matched_all']}/{n['total_gt']} = {n['recall_all']:.1%}")
    print(f"  Core: {n['matched_core']}/{n['total_gt_core']} = {n['recall_core']:.1%}")
    print(f"  Missed core: {n['missed_core']}")
    print(f"\nEDGE RECALL")
    e = evaluation["edges"]
    print(f"  All:  {e['matched_all']}/{e['total_gt']} = {e['recall_all']:.1%}")
    print(f"  Core: {e['matched_core']}/{e['total_gt_core']} = {e['recall_core']:.1%}")
    print(f"  Types: {e['type_distribution']}")
    print(f"{'='*40}")

    # Save eval alongside output
    eval_path = Path(output_path).with_name(
        Path(output_path).stem.replace("_output", "_eval") + ".json"
    )
    with open(eval_path, "w") as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {eval_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Path to extraction output JSON")
    parser.add_argument("ground_truth", help="Path to ground truth JSON")
    args = parser.parse_args()
    run(args.output, args.ground_truth)
