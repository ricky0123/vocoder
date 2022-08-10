from invoke import task


@task
def fmt(c):
    cmds = [
        "autoflake --expand-star-imports --remove-all-unused-imports -ir",
        "isort",
        "black",
    ]
    dirs = ["vocoder", "tests"]
    for dir in dirs:
        for cmd in cmds:
            c.run(f"{cmd} {dir}")
