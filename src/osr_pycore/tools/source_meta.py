from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from osr_pycore.utils.audit import Audit
from osr_pycore.utils.console import ConsoleSink
from osr_pycore.utils.jlog import jline
from osr_pycore.utils.logger import Logger
from osr_pycore.utils.meta import build_meta
from osr_pycore.utils.versioner import build_version_dir


@dataclass(frozen=True, slots=True)
class SourceMetaOut:
    run_dir: str
    meta: dict[str, Any]
    copied_path: str


def _repo_root_from_path(p: Path) -> Path:
    cur = p.resolve()
    if cur.is_file():
        cur = cur.parent
    for _ in range(16):
        if (cur / "uv.lock").is_file() and (cur / "pyproject.toml").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise FileNotFoundError("repo root not found (expected uv.lock and pyproject.toml)")


def _require_file(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return os.path.abspath(path)


def _require_dir(path: str) -> str:
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    return os.path.abspath(path)


def create_source_meta_run(
    *,
    root_dir: str,
    input_dir: str,
    output_root: str,
    src_dir: str,
    script_path: str,
    source_name: str,
    component: str,
) -> SourceMetaOut:
    root_dir = _require_dir(root_dir)
    input_dir = _require_dir(input_dir)
    output_root = os.path.abspath(output_root)
    src_dir = _require_dir(src_dir)
    script_path = _require_file(script_path)

    source_path = _require_file(os.path.join(input_dir, source_name))

    repo_root = _repo_root_from_path(Path(script_path))
    env_path = _require_file(str(repo_root / "uv.lock"))

    params: dict[str, Any] = {
        "component": component,
        "root_dir": root_dir,
        "input_dir": input_dir,
        "output_root": output_root,
        "source_name": source_name,
    }

    meta = build_meta(
        params=params,
        env=env_path,
        script=script_path,
        cfg=source_path,
        src=src_dir,
    )

    run_dir = build_version_dir(output_root, meta)
    audit = Audit.create(run_dir, meta)
    logger = Logger(sinks=[ConsoleSink(), audit])

    try:
        logger.info(jline("stage", component, "start", run_dir=run_dir))
        logger.info(jline("input", component, "root_dir", path=root_dir))
        logger.info(jline("input", component, "input_dir", path=input_dir))
        logger.info(jline("input", component, "source_yaml", path=source_path))

        dst = os.path.join(run_dir, source_name)
        shutil.copy2(source_path, dst)

        logger.info(jline("output", component, "copied", path=dst))
        audit.finish_success()
        return SourceMetaOut(run_dir=run_dir, meta=meta, copied_path=dst)
    except BaseException as e:
        audit.finish_error(e)
        raise


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="source_meta")
    p.add_argument("root_dir")
    p.add_argument("input_dir")
    p.add_argument("output_root")
    p.add_argument("src_dir")
    p.add_argument("--source-name", default="SOURCE.yaml")
    p.add_argument("--component")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    out = create_source_meta_run(
        root_dir=ns.root_dir,
        input_dir=ns.input_dir,
        output_root=ns.output_root,
        src_dir=ns.src_dir,
        script_path=str(Path(__file__).resolve()),
        source_name=ns.source_name,
        component=ns.component,
    )
    print(out.run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
