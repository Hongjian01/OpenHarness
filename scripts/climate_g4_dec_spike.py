"""Day 11 DEC-G4-001 最小实验：安装、读取、magic、截断、伪装、optional 缺失。

本脚本不是生产 CDS client。成功后的契约冻结在 SPEC 与
`src/openharness/climate/formats.py`；fixture 由本脚本生成到
`tests/test_climate/fixtures/`。

验收断言（全部必须可判定）：
1. 当前解释器可 import 选定 NetCDF 库并读取最小 fixture。
2. 读取结果含变量、维度、时间/经纬坐标。
3. 错扩展名、截断、随机 bytes 被拒绝。
4. optional 缺失时可诊断（ImportError → 稳定错误码，不含路径/token）。
5. GRIB：若本机无法安装或无法读取合法消息，记录证据并停止，不得静默省略。
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "test_climate" / "fixtures"

# 报告只打印到 stdout，避免把本机绝对路径写入仓库。

NETCDF_CLASSIC_MAGIC = b"CDF\x01"
NETCDF_64BIT_MAGIC = b"CDF\x02"
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
GRIB_MAGIC = b"GRIB"


def _probe_import(name: str) -> tuple[bool, str]:
    try:
        mod = __import__(name)
        version = getattr(mod, "__version__", "unknown")
        return True, f"{name}=={version} file={getattr(mod, '__file__', '?')}"
    except Exception as exc:  # noqa: BLE001 — spike 需要捕获安装/动态库失败
        return False, f"{name} FAILED: {type(exc).__name__}: {exc}"


def _generate_netcdf(path: Path) -> None:
    from netCDF4 import Dataset

    path.parent.mkdir(parents=True, exist_ok=True)
    with Dataset(path, "w", format="NETCDF4") as ds:
        ds.createDimension("time", 2)
        ds.createDimension("latitude", 2)
        ds.createDimension("longitude", 2)
        times = ds.createVariable("time", "f8", ("time",))
        lats = ds.createVariable("latitude", "f4", ("latitude",))
        lons = ds.createVariable("longitude", "f4", ("longitude",))
        t2m = ds.createVariable("t2m", "f4", ("time", "latitude", "longitude"))
        times.units = "hours since 2025-01-01 00:00:00"
        times.calendar = "gregorian"
        lats.units = "degrees_north"
        lons.units = "degrees_east"
        t2m.units = "K"
        t2m.standard_name = "air_temperature"
        t2m.long_name = "2 metre temperature"
        times[:] = [0.0, 1.0]
        lats[:] = [40.0, 39.0]
        lons[:] = [116.0, 116.25]
        t2m[0, 0, 0] = 273.1
        t2m[0, 0, 1] = 273.2
        t2m[0, 1, 0] = 274.1
        t2m[0, 1, 1] = 274.2
        t2m[1, 0, 0] = 273.3
        t2m[1, 0, 1] = 273.4
        t2m[1, 1, 0] = 274.3
        t2m[1, 1, 1] = 274.4
        ds.Conventions = "CF-1.8"
        ds.title = "ClimWorkflow synthetic NetCDF fixture (not ERA5)"


def _read_netcdf(path: Path) -> dict[str, object]:
    from netCDF4 import Dataset

    with Dataset(path, "r") as ds:
        variables = list(ds.variables.keys())
        dimensions = {name: int(dim.size) for name, dim in ds.dimensions.items()}
        coords = {}
        for name in ("time", "latitude", "longitude"):
            if name not in ds.variables:
                raise AssertionError(f"缺少坐标 {name}")
            coords[name] = list(ds.variables[name][:])
        return {
            "data_model": ds.data_model,
            "variables": variables,
            "dimensions": dimensions,
            "coords": coords,
        }


def _try_grib(path: Path) -> tuple[bool, str]:
    try:
        import eccodes
    except Exception as exc:  # noqa: BLE001
        return False, f"eccodes import failed: {type(exc).__name__}: {exc}"

    try:
        h = eccodes.codes_grib_new_from_samples("regular_ll_pl_grib2")
    except Exception as exc:  # noqa: BLE001
        try:
            h = eccodes.codes_grib_new_from_samples("GRIB2")
        except Exception as exc2:  # noqa: BLE001
            return False, (
                f"eccodes imported ({getattr(eccodes, '__version__', '?')}) "
                f"but sample encode failed: {type(exc).__name__}: {exc}; "
                f"fallback: {type(exc2).__name__}: {exc2}"
            )

    try:
        eccodes.codes_set(h, "Ni", 2)
        eccodes.codes_set(h, "Nj", 2)
        with path.open("wb") as fh:
            eccodes.codes_write(h, fh)
    except Exception as exc:  # noqa: BLE001
        return False, f"eccodes write failed: {type(exc).__name__}: {exc}"
    finally:
        try:
            eccodes.codes_release(h)
        except Exception:
            pass

    try:
        with path.open("rb") as fh:
            gid = eccodes.codes_grib_new_from_file(fh)
        if gid is None:
            return False, "eccodes wrote file but could not re-open"
        try:
            short = eccodes.codes_get(gid, "shortName")
        finally:
            eccodes.codes_release(gid)
        return True, f"eccodes roundtrip ok shortName={short}"
    except Exception as exc:  # noqa: BLE001
        return False, f"eccodes re-open failed: {type(exc).__name__}: {exc}"


def main() -> int:
    lines: list[str] = []
    lines.append(f"python={sys.version}")
    lines.append(f"executable={sys.executable}")
    lines.append(f"platform={sys.platform}")

    for name in ("netCDF4", "h5netcdf", "h5py", "xarray", "cfgrib", "eccodes", "cdsapi"):
        ok, msg = _probe_import(name)
        lines.append(("PASS" if ok else "FAIL") + " import " + msg)

    nc_ok, _ = _probe_import("netCDF4")
    if not nc_ok:
        lines.append("STOP: netCDF4 不可导入，无法完成 fixture spike")
        print("\n".join(lines))
        return 2

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    nc_path = FIXTURE_DIR / "minimal_t2m.nc"
    _generate_netcdf(nc_path)
    raw = nc_path.read_bytes()
    lines.append(f"fixture {nc_path.name} size={len(raw)} magic={raw[:8]!r}")
    if not raw.startswith(HDF5_MAGIC):
        lines.append(f"WARN: expected HDF5/NetCDF4 magic, got {raw[:8]!r}")

    profile = _read_netcdf(nc_path)
    lines.append(f"read profile={profile}")
    assert "t2m" in profile["variables"]
    assert profile["dimensions"] == {"time": 2, "latitude": 2, "longitude": 2}
    lines.append("PASS netcdf read variables/dims/coords")

    truncated = FIXTURE_DIR / "truncated.nc"
    truncated.write_bytes(raw[:32])
    random_nc = FIXTURE_DIR / "random_bytes.nc"
    random_nc.write_bytes(b"\x00\x01\x02\x03" + bytes(range(64)))
    grib_named_nc = FIXTURE_DIR / "grib_magic.nc"
    grib_named_nc.write_bytes(GRIB_MAGIC + b"\x00" * 60)
    nc_named_grib = FIXTURE_DIR / "netcdf_magic.grib"
    nc_named_grib.write_bytes(raw)

    def _expect_reject(path: Path, reason: str) -> None:
        header = path.read_bytes()[:8]
        ext = path.suffix.lower()
        is_nc_magic = header.startswith(NETCDF_CLASSIC_MAGIC) or header.startswith(
            NETCDF_64BIT_MAGIC
        ) or header.startswith(HDF5_MAGIC)
        if ext == ".nc" and is_nc_magic and path.stat().st_size == len(raw):
            raise AssertionError(f"{path.name} should not be the valid fixture")
        if ext == ".nc" and not is_nc_magic:
            lines.append(f"PASS reject {path.name}: ext=.nc but magic={header!r} ({reason})")
            return
        if ext in {".grib", ".grb", ".grib2"} and is_nc_magic:
            lines.append(f"PASS reject {path.name}: ext={ext} but netcdf magic ({reason})")
            return
        if is_nc_magic:
            try:
                _read_netcdf(path)
            except Exception as exc:  # noqa: BLE001
                lines.append(f"PASS parser reject {path.name}: {type(exc).__name__} ({reason})")
                return
            raise AssertionError(f"{path.name} parser unexpectedly succeeded")
        lines.append(f"PASS reject {path.name}: {reason}")

    _expect_reject(truncated, "truncated")
    _expect_reject(random_nc, "random bytes")
    _expect_reject(grib_named_nc, "grib magic with .nc")
    _expect_reject(nc_named_grib, "netcdf magic with .grib")

    # optional 缺失：子解释器无法轻易卸载已导入扩展，记录预期映射
    lines.append(
        "POLICY optional missing: ImportError(netCDF4) -> CLIMATE_DEPENDENCY_MISSING "
        "message 不含绝对路径或 token"
    )

    grib_path = FIXTURE_DIR / "minimal.grib"
    grib_ok, grib_msg = _try_grib(grib_path)
    lines.append(("PASS" if grib_ok else "FAIL") + " grib " + grib_msg)
    if not grib_ok:
        if grib_path.exists():
            grib_path.unlink()
        lines.append("GRIB_DECISION: not feasible on this environment; SPEC must GAP grib")
    else:
        lines.append(f"grib fixture size={grib_path.stat().st_size}")

    lines.append("SPIKE_DONE")
    print("\n".join(lines))
    return 0 if nc_ok else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
