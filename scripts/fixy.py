import subprocess


def main() -> None:
    subprocess.run(["ruff", "format"], check=True)
    subprocess.run(["ruff", "check", "--fix"], check=True)
    subprocess.run(["uv", "run", "pytest"], check=True)
    subprocess.run(
        ["uv", "run", "-m", "scripts.implementation_checker"],
        check=True,
    )


if __name__ == "__main__":
    main()
