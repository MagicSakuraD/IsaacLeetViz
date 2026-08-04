# """
# 200. 岛屿数量
# 中等
# 相关标签
# premium lock icon
# 相关企业
# 给你一个由 '1'（陆地）和 '0'（水）组成的的二维网格，请你计算网格中岛屿的数量。

# 岛屿总是被水包围，并且每座岛屿只能由水平方向和/或竖直方向上相邻的陆地连接形成。

# 此外，你可以假设该网格的四条边均被水包围。

# 示例 1：

# 输入：grid = [
#   ['1','1','1','1','0'],
#   ['1','1','0','1','0'],
#   ['1','1','0','0','0'],
#   ['0','0','0','0','0']
# ]
# 输出：1
# 示例 2：

# 输入：grid = [
#   ['1','1','0','0','0'],
#   ['1','1','0','0','0'],
#   ['0','0','1','0','0'],
#   ['0','0','0','1','1']
# ]
# 输出：3
# """

import asyncio

import numpy as np
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import Cube, GroundPlane
from pxr import Gf, Sdf, UsdGeom

# Isaac Sim default Z-up: grid on XY, height along Z
GRID_ORIGIN = np.array([-0.9, -0.9, 0.0])
CELL_SIZE = 0.18
CELL_GAP = 0.02
CELL_STEP = CELL_SIZE + CELL_GAP
# Lift along +Z when land ("1") is marked visited / becomes water ("0")
VISIT_LIFT = CELL_SIZE * 1.5

LAND_COLOR = np.array([0.2, 0.8, 0.2])   # "1" land: green
WATER_COLOR = np.array([0.2, 0.4, 0.9])  # "0" water: blue
SCAN_COLOR = np.array([1.0, 0.3, 0.3])   # outer-loop cursor: red

# (di, dj) on matrix (row, col): down, up, right, left
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _cell_path(i: int, j: int) -> str:
    return f"/World/Grid/Cell_{i}_{j}"


def _cell_center(i: int, j: int, lifted: bool = False) -> np.ndarray:
    # Local XY layout, then 180 deg around Y: (x, y, z) -> (-x, y, -z); keep +Z height
    local = GRID_ORIGIN + np.array([
        j * CELL_STEP,
        i * CELL_STEP,
        CELL_SIZE / 2.0,
    ])
    z = CELL_SIZE / 2.0 + (VISIT_LIFT if lifted else 0.0)
    return np.array([-local[0], local[1], z])


def _set_cell_color(stage, path: str, color: np.ndarray) -> None:
    prim = stage.GetPrimAtPath(Sdf.Path(path))
    if not prim.IsValid() or not prim.IsA(UsdGeom.Cube):
        return
    cube = UsdGeom.Cube(prim)
    cube.CreateDisplayColorAttr().Set([Gf.Vec3f(*color.tolist())])
    cube.CreateDisplayOpacityAttr().Set([1.0])


def _set_cell_position(path: str, position: np.ndarray) -> None:
    # Wrap existing cube and teleport to world position
    Cube(path).set_world_poses(positions=position.reshape(1, 3))


def _mark_visited(stage, path: str, i: int, j: int) -> None:
    """Mark land as water: blue color + raise on Z (visited)."""
    _set_cell_color(stage, path, WATER_COLOR)
    _set_cell_position(path, _cell_center(i, j, lifted=True))


def _create_grid(stage, grid):
    root_path = Sdf.Path("/World/Grid")
    if stage.GetPrimAtPath(root_path).IsValid():
        stage.RemovePrim(root_path)

    stage_utils.define_prim(str(root_path), "Xform")
    cells = {}

    for i, row in enumerate(grid):
        for j, value in enumerate(row):
            path = _cell_path(i, j)
            color = LAND_COLOR if value == "1" else WATER_COLOR
            Cube(
                path,
                positions=_cell_center(i, j),
                sizes=1.0,
                scales=np.array([CELL_SIZE, CELL_SIZE, CELL_SIZE]),
                colors=color,
            )
            cells[(i, j)] = path

    return cells


async def _refresh(step_delay: float = 0.0, steps: int = 1) -> None:
    await app_utils.update_app_async(steps=steps)
    if step_delay > 0.0:
        await asyncio.sleep(step_delay)


async def visualize_num_islands(grid, step_delay: float = 0.6) -> int:
    try:
        stage = stage_utils.get_current_stage()
    except ValueError as exc:
        raise RuntimeError(
            "Isaac Sim stage is unavailable. Open a Stage first, then run this script in Script Editor."
        ) from exc

    if not stage.GetPrimAtPath("/World").IsValid():
        stage_utils.define_prim("/World", "Xform")
    if not stage.GetPrimAtPath("/World/physicsScene").IsValid():
        stage_utils.define_prim("/World/physicsScene", "PhysicsScene")
    if not stage.GetPrimAtPath("/World/groundPlane").IsValid():
        GroundPlane("/World/groundPlane", positions=[0.0, 0.0, -1.0])

    grid = [list(row) for row in grid]
    rows, cols = len(grid), len(grid[0])
    cells = _create_grid(stage, grid)
    await _refresh(step_delay)

    async def dfs(i: int, j: int) -> None:
        if i < 0 or i >= rows or j < 0 or j >= cols or grid[i][j] != "1":
            return

        # Mark visited: "1" -> "0", blue water + lift on Z
        grid[i][j] = "0"
        _mark_visited(stage, cells[(i, j)], i, j)
        await _refresh(step_delay)

        for di, dj in DIRS:
            await dfs(i + di, j + dj)

    island_count = 0
    for i in range(rows):
        for j in range(cols):
            path = cells[(i, j)]
            # Outer scan cursor: current cell turns red
            _set_cell_color(stage, path, SCAN_COLOR)
            await _refresh(step_delay)

            if grid[i][j] == "1":
                island_count += 1
                print(f"Found island #{island_count}, start=({i}, {j})")
                await dfs(i, j)
            else:
                # Restore water blue (includes already-visited lifted land)
                _set_cell_color(stage, path, WATER_COLOR)
                await _refresh(step_delay)

    return island_count


async def main():
    example_grid = [
        ["1", "1", "0", "0", "0"],
        ["1", "1", "0", "0", "0"],
        ["0", "0", "0", "1", "0"],
        ["0", "0", "0", "1", "1"],
    ]
    islands = await visualize_num_islands(example_grid, step_delay=0.6)
    print(f"Visualization done, island count: {islands}")


# Script Editor / interactive: schedule coroutine directly
asyncio.ensure_future(main())

