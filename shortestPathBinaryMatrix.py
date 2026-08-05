# """
# 1091. Shortest Path in Binary Matrix
# Medium
#
# Given an n x n binary matrix grid, return the length of the shortest clear path
# in the matrix. If there is no clear path, return -1.
#
# A clear path from the top-left (0, 0) to bottom-right (n - 1, n - 1) must:
# - visit only cells with value 0
# - move in one of 8 directions between adjacent cells
# Path length = number of visited cells.
#
# Example 1: grid = [[0,1],[1,0]] -> 2
# Example 2: grid = [[0,0,0],[1,1,0],[1,1,0]] -> 4
# Example 3: grid = [[1,0,0],[1,1,0],[1,1,0]] -> -1
#
# ### Visualization legend
# | State | Look |
# |-------|------|
# | 0 open | green cube |
# | 1 blocked | dark gray cube |
# | BFS current (dequeue) | red highlight |
# | BFS visited / enqueued | cyan + lift on +Z |
# | Shortest path cells | orange + higher lift |
#
# Tunables: CELL_SIZE, VISIT_LIFT, PATH_LIFT, step_delay
# """

from __future__ import annotations

import asyncio
from collections import deque
from typing import Dict, List, Optional, Tuple

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
VISIT_LIFT = CELL_SIZE * 1.2
PATH_LIFT = CELL_SIZE * 2.4

OPEN_COLOR = np.array([0.2, 0.8, 0.2])      # 0: open / passable
BLOCK_COLOR = np.array([0.25, 0.25, 0.28])  # 1: blocked
CURRENT_COLOR = np.array([1.0, 0.3, 0.3])   # BFS pop: red
VISITED_COLOR = np.array([0.2, 0.75, 0.9])  # visited: cyan
PATH_COLOR = np.array([1.0, 0.55, 0.1])     # shortest path: orange

# 8 directions (row, col)
DIRS = (
    (0, 1),
    (1, 0),
    (0, -1),
    (-1, 0),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)


class Solution:
    def shortestPathBinaryMatrix(self, grid: List[List[int]]) -> int:
        if not grid or grid[0][0] == 1: # 如果矩阵为空或者起点是1，则直接返回-1
            return -1
        n = len(grid) # 矩阵的边长
        if grid[n - 1][n - 1] == 1: # 如果终点是1，则直接返回-1
            return -1
        if n == 1: # 如果矩阵只有一个元素，则直接返回1
            return 1

        queue = deque([(0, 0, 1)]) # 队列中存储的是当前位置和路径长度
        visited = {(0, 0)} # 记录已经访问过的位置, 用集合来存储，因为集合的查找时间复杂度是O(1)
        while queue:
            x, y, path_length = queue.popleft() # 取出队列中的当前位置和路径长度
            if x == n - 1 and y == n - 1: # 如果当前位置是终点，则返回路径长度
                return path_length
            for dx, dy in DIRS: # 遍历8个方向
                nx, ny = x + dx, y + dy
                if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in visited and grid[nx][ny] == 0: # 如果下一个位置在矩阵范围内，且没有访问过，且值为0
                    visited.add((nx, ny)) # 将下一个位置标记为已访问
                    queue.append((nx, ny, path_length + 1)) # 将下一个位置和路径长度加入队列
        return -1 # 如果无法到达终点，则返回-1      


def _cell_path(i: int, j: int) -> str: 
    return f"/World/Grid/Cell_{i}_{j}" # 返回当前位置的path


def _cell_center(i: int, j: int, lift: float = 0.0) -> np.ndarray:
    # Local XY layout, then 180 deg around Y; keep +Z height
    local = GRID_ORIGIN + np.array([j * CELL_STEP, i * CELL_STEP, CELL_SIZE / 2.0]) # 计算当前位置的中心点
    return np.array([-local[0], local[1], CELL_SIZE / 2.0 + lift]) # 返回当前位置的中心点


def _set_cell_color(stage, path: str, color: np.ndarray) -> None:
    prim = stage.GetPrimAtPath(Sdf.Path(path)) # 获取当前位置的prim
    if not prim.IsValid() or not prim.IsA(UsdGeom.Cube): # 如果当前位置的prim无效或者不是立方体，则返回
        return
    cube = UsdGeom.Cube(prim) # 获取当前位置的立方体
    cube.CreateDisplayColorAttr().Set([Gf.Vec3f(*color.tolist())]) # 设置当前位置的立方体的颜色
    cube.CreateDisplayOpacityAttr().Set([1.0]) # 设置当前位置的立方体的透明度


def _set_cell_position(path: str, position: np.ndarray) -> None:
    Cube(path).set_world_poses(positions=position.reshape(1, 3)) # 设置当前位置的立方体的世界位置


def _style_cell(stage, path: str, i: int, j: int, color: np.ndarray, lift: float) -> None:
    _set_cell_color(stage, path, color) # 设置当前位置的立方体的颜色
    _set_cell_position(path, _cell_center(i, j, lift=lift)) # 设置当前位置的立方体的世界位置


def _create_grid(stage, grid: List[List[int]]):
    root_path = Sdf.Path("/World/Grid") # 获取当前位置的path
    if stage.GetPrimAtPath(root_path).IsValid(): # 如果当前位置的prim有效，则删除当前位置的prim
        stage.RemovePrim(root_path)

    stage_utils.define_prim(str(root_path), "Xform")
    cells = {} # 记录当前位置的立方体

    for i, row in enumerate(grid): # 遍历矩阵
        for j, value in enumerate(row): # 遍历当前行
            path = _cell_path(i, j) # 获取当前位置的path
            color = BLOCK_COLOR if value == 1 else OPEN_COLOR # 设置当前位置的立方体的颜色
            Cube(path, positions=_cell_center(i, j), sizes=1.0, scales=np.array([CELL_SIZE, CELL_SIZE, CELL_SIZE]), colors=color)
            cells[(i, j)] = path # 记录当前位置的立方体

    return cells # 返回当前位置的立方体


async def _refresh(step_delay: float = 0.0, steps: int = 1) -> None:
    await app_utils.update_app_async(steps=steps) # 更新应用程序
    if step_delay > 0.0: # 如果步长大于0，则等待步长时间
        await asyncio.sleep(step_delay) # 等待步长时间


def _ensure_scene(stage) -> None:
    if not stage.GetPrimAtPath("/World").IsValid(): # 如果当前位置的prim无效，则定义当前位置的prim
        stage_utils.define_prim("/World", "Xform")
    if not stage.GetPrimAtPath("/World/physicsScene").IsValid(): # 如果当前位置的prim无效，则定义当前位置的prim
        stage_utils.define_prim("/World/physicsScene", "PhysicsScene")
    if not stage.GetPrimAtPath("/World/groundPlane").IsValid(): # 如果当前位置的prim无效，则定义当前位置的prim
        GroundPlane("/World/groundPlane", positions=[0.0, 0.0, -1.0]) # 定义当前位置的地面



def _reconstruct_path(
    parent: Dict[Tuple[int, int], Optional[Tuple[int, int]]],
    end: Tuple[int, int],
) -> List[Tuple[int, int]]:
    path: List[Tuple[int, int]] = [] # 记录当前路径
    cur: Optional[Tuple[int, int]] = end # 记录当前位置
    while cur is not None: # 如果当前位置不为空
        path.append(cur) # 将当前位置加入路径
        cur = parent.get(cur) # 获取当前位置的父位置
    path.reverse() # 反转路径，因为是从终点开始，找到最短路径，所以需要反转路径
    return path # 返回当前路径


async def visualize_shortest_path_binary_matrix(
    grid: List[List[int]],
    step_delay: float = 1.45,
) -> int:
    """BFS shortest clear path with Isaac Sim visualization. Returns path length or -1."""
    try:
        stage = stage_utils.get_current_stage()
    except ValueError as exc:
        raise RuntimeError( # 如果当前位置的prim无效，则定义当前位置的prim
            "Isaac Sim stage is unavailable. Open a Stage first, then run this script in Script Editor."
        ) from exc

    _ensure_scene(stage)
    grid = [list(row) for row in grid] # 将矩阵转换为列表
    n = len(grid) # 矩阵的边长
    cells = _create_grid(stage, grid)
    await _refresh(step_delay)

    if grid[0][0] == 1 or grid[n - 1][n - 1] == 1: # 如果起点或终点是1，则直接返回-1
        print("No path: start or end is blocked")
        return -1
    if n == 1: # 如果矩阵只有一个元素，则直接返回1
        _style_cell(stage, cells[(0, 0)], 0, 0, PATH_COLOR, PATH_LIFT) # 设置当前位置的立方体的颜色
        await _refresh(step_delay) # 更新应用程序
        print("Path length: 1") # 打印路径长度
        return 1 # 返回路径长度

    queue = deque([(0, 0, 1)]) # 队列中存储的是当前位置和路径长度
    visited = {(0, 0)} # 记录已经访问过的位置
    parent: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {(0, 0): None} # 记录当前位置的父位置

    # Mark start as visited (cyan + lift)
    _style_cell(stage, cells[(0, 0)], 0, 0, VISITED_COLOR, VISIT_LIFT) # 设置当前位置的立方体的颜色，起点是紫色的
    await _refresh(step_delay) # 更新应用程序
    print("BFS start at (0, 0)") # 打印开始位置

    while queue:
        x, y, path_length = queue.popleft() # 取出队列中的当前位置和路径长度
        path = cells[(x, y)] # 获取当前位置的立方体

        # Current BFS cell
        _style_cell(stage, path, x, y, CURRENT_COLOR, VISIT_LIFT) # 设置当前位置的立方体的颜色
        await _refresh(step_delay) # 更新应用程序
        print(f"Visit ({x}, {y}), dist={path_length}") # 打印当前位置和路径长度

        if x == n - 1 and y == n - 1: # 如果当前位置是终点，则返回路径长度
            shortest = _reconstruct_path(parent, (x, y)) # 重建路径, 从终点开始，找到最短路径
            print(f"Reached end, reconstructing path len={path_length}: {shortest}")
            for pi, pj in shortest:
                _style_cell(stage, cells[(pi, pj)], pi, pj, PATH_COLOR, PATH_LIFT) # 设置当前位置的立方体的颜色
                await _refresh(step_delay)
            return path_length # 返回路径长度

        # Restore visited look after red flash
        _style_cell(stage, path, x, y, VISITED_COLOR, VISIT_LIFT) # 设置当前位置的立方体的颜色

        for dx, dy in DIRS: # 遍历8个方向
            nx, ny = x + dx, y + dy
            if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in visited and grid[nx][ny] == 0:
                visited.add((nx, ny)) # 将下一个位置标记为已访问
                parent[(nx, ny)] = (x, y) # 记录当前位置的父位置
                queue.append((nx, ny, path_length + 1)) # 将下一个位置和路径长度加入队列
                _style_cell(stage, cells[(nx, ny)], nx, ny, VISITED_COLOR, VISIT_LIFT) # 设置当前位置的立方体的颜色     
                await _refresh(step_delay * 0.5)

    print("No clear path found") # 打印没有找到路径
    return -1


async def main():
    # Example 2 from the problem statement
    example_grid = [
    [0, 0, 0, 0, 0, 0],
    [1, 1, 0, 1, 1, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 0],
    [0, 0, 0, 0, 0, 0],
    [0, 1, 1, 1, 1, 0]
    ]
    length = await visualize_shortest_path_binary_matrix(example_grid, step_delay= 2.45)
    print(f"Visualization done, shortest path length: {length}")


# Script Editor / interactive: schedule coroutine directly
asyncio.ensure_future(main())
