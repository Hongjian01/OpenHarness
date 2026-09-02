"""允许 `python -m evals` 从仓库根目录运行。"""

from evals.climate.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
