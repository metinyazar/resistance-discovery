import argparse

from src.gdsc import load_gdsc_snapshot


def main():
    parser = argparse.ArgumentParser(description="Load a normalized GDSC snapshot CSV into DuckDB.")
    parser.add_argument("csv_path", help="Path to the normalized GDSC snapshot CSV")
    args = parser.parse_args()
    load_gdsc_snapshot(args.csv_path)


if __name__ == "__main__":
    main()
