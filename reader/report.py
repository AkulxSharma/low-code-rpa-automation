"""One report for n8n to call: measured aggregates plus the replay line.

Prints markdown to stdout. Counts and timings only.
"""
import sys

from reader import replay, stats


def build(path):
    rows = stats.load(path)
    return stats.render(stats.summarize(rows)) + "\n" + replay.render(replay.replay(rows))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m reader.report <path to sweep-stats.csv>")
    sys.stdout.write(build(sys.argv[1]))
