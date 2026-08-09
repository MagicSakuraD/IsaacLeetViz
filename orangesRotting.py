# """
# 994. Rotting Oranges
# Medium
#
# In an m x n grid, each cell is one of:
#   0 - empty
#   1 - fresh orange
#   2 - rotten orange
# Every minute, any fresh orange 4-directionally adjacent to a rotten orange becomes rotten.
# Return the minimum minutes until no fresh orange remains, or -1 if impossible.
#
# ### Visualization legend
# | State | Look |
# |-------|------|
# | 0 empty | dark flat pad |
# | 1 fresh | orange_var.usd ref, appearance=fresh |
# | 2 rotten | orange_var.usd ref, appearance=rotten |
# | just infected | switch to rotten + lift on +Z |
# | BFS source | pad flashes red |
#
# Asset: C:/OMEN/USD/blenderDAY/orange/orange_var.usd
# Tunables: CELL_SIZE, ORANGE_SCALE, INFECT_LIFT, step_delay
# """

from __future__ import annotations

import asyncio
from collections import deque
from typing import Dict, List, Optional, Tuple

import numpy as np
import omni.usd
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import Cube, GroundPlane
from isaacsim.core.experimental.prims import XformPrim
from pxr import Gf, Sdf, Usd, UsdGeom

# Isaac Sim default Z-up: grid on XY, height along Z
GRID_ORIGIN = np.array([-0.9, -0.9, 0.0])
CELL_SIZE = 0.35
CELL_GAP = 0.08
CELL_STEP = CELL_SIZE + CELL_GAP
INFECT_LIFT = CELL_SIZE * 0.9
PAD_HEIGHT = 0.02
ORANGE_SCALE = 0.12  # blender orange is often large; shrink to fit cell

ORANGE_USD = "C:/OMEN/USD/blenderDAY/orange/orange_var.usd"
GRID_ROOT = "/World/OrangeGrid"
VARIANT_SET = "appearance"
VARIANT_FRESH = "fresh"
VARIANT_ROTTEN = "rotten"

EMPTY_COLOR = np.array([0.22, 0.22, 0.25])
FRESH_PAD_COLOR = np.array([0.15, 0.45, 0.2])
ROTTEN_PAD_COLOR = np.array([0.45, 0.25, 0.1])
ACTIVE_PAD_COLOR = np.array([1.0, 0.3, 0.3])

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Solution:
    def orangesRotting(self, grid: List[List[int]]) -> int:
        rows, cols = len(grid), len(grid[0])
        queue = deque()
        fresh = 0

        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 1:
                    fresh += 1
                elif grid[r][c] == 2:
                    queue.append((r, c))

        if fresh == 0:
            return 0

        minutes = 0
        while queue:
            size = len(queue)
            infected = False
            for _ in range(size):
                r, c = queue.popleft()
                for dr, dc in DIRS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                        grid[nr][nc] = 2
                        fresh -= 1
                        queue.append((nr, nc))
                        infected = True
            if infected:
                minutes += 1

        return minutes if fresh == 0 else -1


def _cell_pad_path(i: int, j: int) -> str:
    return f"{GRID_ROOT}/Pad_{i}_{j}"


def _cell_orange_path(i: int, j: int) -> str:
    return f"{GRID_ROOT}/Orange_{i}_{j}"


def _cell_center(i: int, j: int, lift: float = 0.0) -> np.ndarray:
    local = GRID_ORIGIN + np.array([j * CELL_STEP, i * CELL_STEP, 0.0])
    return np.array([-local[0], local[1], lift])


def _flush_stage(stage) -> None:
    flush = getattr(stage, "Flush", None)
    if callable(flush):
        flush()


def _reset_scene(stage) -> None:
    """Clear previous OrangeGrid (and optional leftover /World/orange clutter)."""
    for path in (GRID_ROOT, "/World/orange"):
        prim = stage.GetPrimAtPath(path)
        if prim.IsValid():
            print(f"Reset: removing {path}")
            stage.RemovePrim(path)
    _flush_stage(stage)


def _find_variant_prim(stage, root_path: str) -> Optional[Usd.Prim]:
    root = stage.GetPrimAtPath(root_path)
    if not root.IsValid():
        return None
    if root.GetVariantSets().HasVariantSet(VARIANT_SET):
        return root
    for prim in Usd.PrimRange(root):
        if prim.GetVariantSets().HasVariantSet(VARIANT_SET):
            return prim
    return None


def _set_appearance(stage, orange_root_path: str, selection: str) -> None:
    prim = _find_variant_prim(stage, orange_root_path)
    if prim is None:
        print(f"Warn: variant set '{VARIANT_SET}' not found under {orange_root_path}")
        return

    variant_set = prim.GetVariantSet(VARIANT_SET)
    names = list(variant_set.GetVariantNames())
    if selection not in names:
        print(f"Warn: variant '{selection}' not in {names} on {prim.GetPath()}")
        return

    variant_set.SetVariantSelection(selection)
    _flush_stage(stage)


def _resolve_variants_from_asset() -> Tuple[str, str]:
    """Read variant names from the USD asset layer (no stage template required)."""
    global VARIANT_FRESH, VARIANT_ROTTEN
    layer = Sdf.Layer.FindOrOpen(ORANGE_USD)
    if not layer:
        print(f"Warn: cannot open {ORANGE_USD}, using defaults")
        return VARIANT_FRESH, VARIANT_ROTTEN

    # Temporary stage just to query variant names
    tmp = Usd.Stage.Open(ORANGE_USD)
    if not tmp:
        return VARIANT_FRESH, VARIANT_ROTTEN

    names: List[str] = []
    for prim in tmp.Traverse():
        if prim.GetVariantSets().HasVariantSet(VARIANT_SET):
            names = list(prim.GetVariantSet(VARIANT_SET).GetVariantNames())
            print(f"Asset variants on {prim.GetPath()}: {names}")
            break

    if not names:
        print("Warn: no appearance variants in asset, using defaults")
        return VARIANT_FRESH, VARIANT_ROTTEN

    rotten = next((n for n in names if "rotten" in n.lower()), names[-1])
    fresh = next((n for n in names if "fresh" in n.lower() or "real" in n.lower()), None)
    if fresh is None:
        fresh = next((n for n in names if n != rotten), names[0])

    VARIANT_FRESH, VARIANT_ROTTEN = fresh, rotten
    print(f"Resolved variants: fresh={VARIANT_FRESH}, rotten={VARIANT_ROTTEN}")
    return VARIANT_FRESH, VARIANT_ROTTEN


def _set_pad_color(stage, path: str, color: np.ndarray) -> None:
    prim = stage.GetPrimAtPath(Sdf.Path(path))
    if not prim.IsValid() or not prim.IsA(UsdGeom.Cube):
        return
    cube = UsdGeom.Cube(prim)
    cube.CreateDisplayColorAttr().Set([Gf.Vec3f(*color.tolist())])
    cube.CreateDisplayOpacityAttr().Set([1.0])


def _place_orange(path: str, position: np.ndarray) -> None:
    """Reset xform ops and set world position/scale so oranges are not stacked at origin."""
    xform = XformPrim(
        path,
        positions=position.reshape(1, 3),
        scales=np.array([[ORANGE_SCALE, ORANGE_SCALE, ORANGE_SCALE]]),
        reset_xform_op_properties=True,
    )
    return xform


def _spawn_orange(stage, dest_path: str, selection: str, position: np.ndarray) -> Optional[str]:
    if stage.GetPrimAtPath(dest_path).IsValid():
        stage.RemovePrim(dest_path)

    try:
        stage_utils.add_reference_to_stage(
            usd_path=ORANGE_USD,
            path=dest_path,
            variants=[(VARIANT_SET, selection)],
        )
    except Exception as exc:
        print(f"Warn: add_reference_to_stage failed for {dest_path}: {exc}")
        # Fallback without variants kw (older API)
        try:
            stage_utils.add_reference_to_stage(usd_path=ORANGE_USD, path=dest_path)
        except Exception as exc2:
            print(f"Warn: spawn failed {dest_path}: {exc2}")
            return None
        _set_appearance(stage, dest_path, selection)

    _place_orange(dest_path, position)
    _set_appearance(stage, dest_path, selection)
    return dest_path


def _create_grid(stage, grid: List[List[int]]):
    _reset_scene(stage)
    stage_utils.define_prim(GRID_ROOT, "Xform")
    _resolve_variants_from_asset()

    cells: Dict[Tuple[int, int], Dict[str, Optional[str]]] = {}

    for i, row in enumerate(grid):
        for j, value in enumerate(row):
            pad_path = _cell_pad_path(i, j)
            pad_pos = _cell_center(i, j, lift=PAD_HEIGHT / 2.0)
            pad_color = EMPTY_COLOR
            if value == 1:
                pad_color = FRESH_PAD_COLOR
            elif value == 2:
                pad_color = ROTTEN_PAD_COLOR

            Cube(
                pad_path,
                positions=pad_pos,
                sizes=1.0,
                scales=np.array([CELL_SIZE * 0.9, CELL_SIZE * 0.9, PAD_HEIGHT]),
                colors=pad_color,
            )

            orange_path = None
            if value in (1, 2):
                orange_path = _cell_orange_path(i, j)
                selection = VARIANT_FRESH if value == 1 else VARIANT_ROTTEN
                pos = _cell_center(i, j, lift=PAD_HEIGHT + CELL_SIZE * 0.25)
                orange_path = _spawn_orange(stage, orange_path, selection, pos)

            cells[(i, j)] = {"pad": pad_path, "orange": orange_path, "state": value}
            print(f"Cell ({i},{j}) value={value} orange={orange_path} pos={_cell_center(i, j)}")

    _flush_stage(stage)
    return cells


async def _refresh(step_delay: float = 0.0, steps: int = 1) -> None:
    await app_utils.update_app_async(steps=steps)
    if step_delay > 0.0:
        await asyncio.sleep(step_delay)


def _ensure_scene(stage) -> None:
    if not stage.GetPrimAtPath("/World").IsValid():
        stage_utils.define_prim("/World", "Xform")
    if not stage.GetPrimAtPath("/World/physicsScene").IsValid():
        stage_utils.define_prim("/World/physicsScene", "PhysicsScene")
    if not stage.GetPrimAtPath("/World/groundPlane").IsValid():
        GroundPlane("/World/groundPlane", positions=[0.0, 0.0, -1.0])


async def _infect_cell(stage, cells, i: int, j: int, step_delay: float) -> None:
    info = cells[(i, j)]
    orange_path = info["orange"]
    pad_path = info["pad"]

    _set_pad_color(stage, pad_path, ACTIVE_PAD_COLOR)
    await _refresh(step_delay * 0.35)

    lift_pos = _cell_center(i, j, lift=PAD_HEIGHT + CELL_SIZE * 0.25 + INFECT_LIFT)

    if orange_path is None or not stage.GetPrimAtPath(orange_path).IsValid():
        orange_path = _cell_orange_path(i, j)
        orange_path = _spawn_orange(stage, orange_path, VARIANT_ROTTEN, lift_pos)
        info["orange"] = orange_path
        if orange_path is None:
            _set_pad_color(stage, pad_path, ROTTEN_PAD_COLOR)
            return
    else:
        _set_appearance(stage, orange_path, VARIANT_ROTTEN)
        _place_orange(orange_path, lift_pos)

    info["state"] = 2
    _set_pad_color(stage, pad_path, ROTTEN_PAD_COLOR)
    await _refresh(step_delay)


async def visualize_oranges_rotting(grid: List[List[int]], step_delay: float = 0.55) -> int:
    """Multi-source BFS rotting oranges with orange_var.usd appearance variants."""
    try:
        stage = stage_utils.get_current_stage()
    except ValueError as exc:
        raise RuntimeError(
            "Isaac Sim stage is unavailable. Open a Stage first, then run this script in Script Editor."
        ) from exc

    stage = omni.usd.get_context().get_stage() or stage
    _ensure_scene(stage)

    grid = [list(row) for row in grid]
    rows, cols = len(grid), len(grid[0])
    cells = _create_grid(stage, grid)
    await _refresh(step_delay)

    queue = deque()
    fresh = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                fresh += 1
            elif grid[r][c] == 2:
                queue.append((r, c))

    print(f"Init: fresh={fresh}, rotten_sources={len(queue)}")
    print("Hold initial state for 2.0s before BFS...")
    await _refresh(2.0)

    if fresh == 0:
        print("No fresh oranges, minutes=0")
        return 0

    minutes = 0
    while queue:
        size = len(queue)
        infected = False
        print(f"--- minute frontier size={size} ---")

        for _ in range(size):
            r, c = queue.popleft()
            pad = cells[(r, c)]["pad"]
            _set_pad_color(stage, pad, ACTIVE_PAD_COLOR)
            await _refresh(step_delay * 0.25)
            _set_pad_color(stage, pad, ROTTEN_PAD_COLOR)

            for dr, dc in DIRS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 1:
                    grid[nr][nc] = 2
                    fresh -= 1
                    queue.append((nr, nc))
                    infected = True
                    print(f"Infect ({nr}, {nc}), fresh_left={fresh}")
                    await _infect_cell(stage, cells, nr, nc, step_delay)

        if infected:
            minutes += 1
            print(f"Minute -> {minutes}")
            await _refresh(step_delay)

    result = minutes if fresh == 0 else -1
    print(f"Done: minutes={result}, fresh_left={fresh}")
    return result


async def main():
    # LeetCode example: answer 4
    example_grid = [
        [2, 1, 1],
        [1, 1, 0],
        [0, 1, 1],
    ]
    minutes = await visualize_oranges_rotting(example_grid, step_delay=0.55)
    print(f"Visualization done, minutes: {minutes}")


# Script Editor / interactive: schedule coroutine directly
asyncio.ensure_future(main())
