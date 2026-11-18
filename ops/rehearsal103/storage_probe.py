"""Stat-only fixed read-only store roots. Never emit paths or native errors."""
import json
import os
from pathlib import Path
import stat
import sys

ROOTS = {"prometheus": Path("/metrics"), "grafana": Path("/grafana")}


class ProbeError(Exception):
    pass


def checked_stat(path, device=None):
    value = path.lstat()
    if stat.S_ISLNK(value.st_mode):
        raise ProbeError("symlink")
    if device is not None and value.st_dev != device:
        raise ProbeError("unexpected-device")
    return value


def allocated_tree(path, *, optional=False):
    try:
        root = checked_stat(path)
    except FileNotFoundError:
        if optional:
            return 0, False
        raise
    if not stat.S_ISDIR(root.st_mode):
        raise ProbeError("not-directory")
    def fail(error):
        raise error
    total = 0
    for directory, dirs, files in os.walk(path, followlinks=False, onerror=fail):
        value = checked_stat(Path(directory), root.st_dev)
        total += getattr(value, "st_blocks", 0) * 512 if hasattr(value, "st_blocks") else value.st_size
        for name in dirs:
            checked_stat(Path(directory) / name, root.st_dev)
        for name in files:
            value = checked_stat(Path(directory) / name, root.st_dev)
            total += value.st_blocks * 512 if hasattr(value, "st_blocks") else value.st_size
    return total, True


def measure(role):
    if role not in ROOTS:
        raise ProbeError("invalid-role")
    root = ROOTS[role]
    total, _ = allocated_tree(root)
    result = {"status": "ok", "role": role, "allocated_bytes": total, "subsets": {}, "subset_present": {}}
    if role == "prometheus":
        for name in ("wal", "chunks_head"):
            result["subsets"][name], result["subset_present"][name] = allocated_tree(root / name, optional=True)
    return result


def category(error):
    if isinstance(error, ProbeError):
        return str(error) if str(error) in {"symlink", "unexpected-device", "not-directory", "invalid-role"} else "other"
    if isinstance(error, PermissionError):
        return "permission-denied"
    if isinstance(error, FileNotFoundError):
        return "not-found"
    return "other"


def access():
    result = {}
    for role, path in ROOTS.items():
        value = checked_stat(path)
        entry = {"owner_uid": value.st_uid, "owner_gid": value.st_gid}
        try:
            measure(role)
            entry["legacy_category"] = "readable"
        except Exception as error:
            entry["legacy_category"] = category(error)
        result[role] = entry
    return {"status": "ok", "roles": result}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        if args == ["access"]:
            result = access()
        elif len(args) == 2 and args[0] == "measure" and args[1] in ROOTS:
            result = measure(args[1])
        else:
            raise ProbeError("invalid-role")
    except Exception as error:
        print(json.dumps({"status": "error", "category": category(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
