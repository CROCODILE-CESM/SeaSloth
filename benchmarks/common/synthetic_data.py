"""
Synthetic grid and data factories shared across all benchmark suites.

All functions use a fixed RNG seed so results are deterministic across runs.
Grids are designed to match the coordinate conventions that xESMF and mom6_forge expect.
"""

import numpy as np
import xarray as xr

_RNG = np.random.default_rng(42)


def make_rect_grid(
    nlon: int,
    nlat: int,
    lon0: float = 0.0,
    lon1: float = 10.0,
    lat0: float = 0.0,
    lat1: float = 10.0,
) -> xr.Dataset:
    """Rectilinear source grid with 1D lon/lat and cell-edge bounds.

    Includes lon_b/lat_b (n+1 edges) and CF units attributes so xESMF's
    conservative method can find and use the bounds via cf_xarray.
    """
    lon_b = np.linspace(lon0, lon1, nlon + 1)
    lat_b = np.linspace(lat0, lat1, nlat + 1)
    lon = 0.5 * (lon_b[:-1] + lon_b[1:])
    lat = 0.5 * (lat_b[:-1] + lat_b[1:])
    return xr.Dataset(
        {
            "lon": ("lon", lon, {"units": "degrees_east"}),
            "lat": ("lat", lat, {"units": "degrees_north"}),
            "lon_b": ("lon_b", lon_b),
            "lat_b": ("lat_b", lat_b),
        }
    )


def make_curvilinear_grid(nlon: int, nlat: int) -> xr.Dataset:
    """
    2D curvilinear destination grid matching the coordinate layout that mom6_forge's
    Grid class produces (ny x nx arrays of lon/lat).

    Includes 2D lon_b/lat_b corner arrays (ny+1 x nx+1) required by xESMF's
    conservative regridding method.
    """
    lon_b_1d = np.linspace(0.0, 10.0, nlon + 1)
    lat_b_1d = np.linspace(0.0, 10.0, nlat + 1)
    lon2d, lat2d = np.meshgrid(
        0.5 * (lon_b_1d[:-1] + lon_b_1d[1:]),
        0.5 * (lat_b_1d[:-1] + lat_b_1d[1:]),
    )
    lon_b2d, lat_b2d = np.meshgrid(lon_b_1d, lat_b_1d)
    return xr.Dataset(
        {
            "lon": (["ny", "nx"], lon2d, {"units": "degrees_east"}),
            "lat": (["ny", "nx"], lat2d, {"units": "degrees_north"}),
            "lon_b": (["nyp", "nxp"], lon_b2d),
            "lat_b": (["nyp", "nxp"], lat_b2d),
        }
    )


def make_locstream_grid(n: int) -> xr.Dataset:
    """
    1D locstream destination — matches CrocoDash's OBC boundary usage where
    xe.Regridder is called with locstream_out=True.
    """
    return xr.Dataset(
        {
            "lon": ("ncells", np.linspace(0.0, 10.0, n)),
            "lat": ("ncells", np.linspace(0.0, 5.0, n)),
        }
    )


def make_data_variable(
    source_grid: xr.Dataset,
    ntime: int = 12,
    nvars: int = 1,
) -> xr.Dataset:
    """
    Add scalar field(s) to a grid dataset. Chooses dimension names automatically
    from the grid's existing dims (handles both rectilinear and curvilinear).
    """
    sizes = source_grid.sizes
    if "lon" in sizes and "lat" in sizes:
        spatial_dims = ["lat", "lon"]
        shape = (ntime, sizes["lat"], sizes["lon"])
    elif "ny" in sizes and "nx" in sizes:
        spatial_dims = ["ny", "nx"]
        shape = (ntime, sizes["ny"], sizes["nx"])
    elif "ncells" in sizes:
        spatial_dims = ["ncells"]
        shape = (ntime, sizes["ncells"])
    else:
        raise ValueError(f"Unrecognized grid dims: {list(sizes)}")

    ds = source_grid.copy()
    var_names = ["temperature"] if nvars == 1 else [f"var_{i}" for i in range(nvars)]
    for name in var_names:
        data = _RNG.standard_normal(shape).astype(np.float32)
        ds[name] = xr.DataArray(data, dims=["time"] + spatial_dims)
    return ds


def make_supergrid(nx: int, ny: int) -> xr.Dataset:
    """
    Minimal MOM6 supergrid (2ny+1 x 2nx+1) for mom6_forge Grid benchmarks.
    Uses a simple lat-lon layout — not a realistic projection but correct shape.
    """
    snx, sny = 2 * nx + 1, 2 * ny + 1
    x = np.linspace(0.0, 10.0, snx)
    y = np.linspace(0.0, 10.0, sny)
    xx, yy = np.meshgrid(x, y)
    return xr.Dataset(
        {
            "x": (["nyp", "nxp"], xx.astype(np.float64)),
            "y": (["nyp", "nxp"], yy.astype(np.float64)),
            "dx": (["nyp", "nxp"], np.full((sny, snx), 10000.0 / snx)),
            "dy": (["nyp", "nxp"], np.full((sny, snx), 10000.0 / sny)),
            "angle_dx": (["nyp", "nxp"], np.zeros((sny, snx))),
            "area": (["ny", "nx"], np.full((ny, nx), 1e8)),
        }
    )
