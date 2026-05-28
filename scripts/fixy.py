import subprocess


def main() -> None:
    subprocess.run(["ruff", "format"])
    subprocess.run(["ruff", "check", "--fix"])
    subprocess.run(["uv", "run", "-m", "unittest", "discover"])


if __name__ == "__main__":
    main()
