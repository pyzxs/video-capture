"""自动数据库迁移 — 在 init_db() 时按顺序执行。"""

import importlib
import pkgutil


def _run_all(engine):
    """按模块名排序，执行所有 src.migrations 中的迁移。"""
    import src.migrations as pkg

    modules = sorted(
        (m for m in pkgutil.iter_modules(pkg.__path__) if m.name.startswith("0")),
        key=lambda m: m.name,
    )
    for mod_info in modules:
        mod = importlib.import_module(f"src.migrations.{mod_info.name}")
        if hasattr(mod, "run"):
            mod.run(engine)
