# IsaacLeetViz

用 [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim) 在 3D 场景里**可视化 LeetCode 数据结构与算法题**的学习项目。

通过方块、颜色与空间动画，把抽象的遍历 / 搜索过程变成可观察的仿真，方便理解算法每一步在做什么。

## 环境要求

- NVIDIA Isaac Sim（建议 4.5+ / 与 `isaacsim.core.experimental` API 兼容的版本）
- 在 Isaac Sim 中打开一个 Stage 后再运行脚本
- 运行方式：`Window > Script Editor`（交互式 Python），不要当作普通系统 Python 直接跑

## 快速开始

1. 启动 Isaac Sim，新建或打开一个 Stage  
2. 打开 **Window → Script Editor**  
3. 打开本仓库中的题目脚本（例如 `numIslands.py`）  
4. 点击 Run / 执行脚本  
5. 在视口中观察可视化过程；英文日志会打印在 Isaac Sim 终端（终端对中文支持不佳）

## 当前题目

| 文件 | 题目 | 思路 |
|------|------|------|
| `numIslands.py` | [200. Number of Islands](https://leetcode.com/problems/number-of-islands/) | DFS 淹没岛屿 |

### 岛屿数量可视化约定

| 状态 | 表现 |
|------|------|
| `"1"` 陆地 | 绿色方块 |
| `"0"` 水 | 蓝色方块 |
| 外层双重循环扫到的当前格 | 红色高亮 |
| DFS 标记访问（`"1"` → `"0"`） | 变蓝，并沿 **+Z** 抬升 |

可调参数见脚本顶部：`CELL_SIZE`、`VISIT_LIFT`、`step_delay` 等。

## 项目结构

```text
IsaacLeetViz/
├── README.md
├── .gitignore
├── .gitattributes
└── numIslands.py          # 200. Number of Islands
```

后续可按题目增加脚本，例如 `twoSum.py`、`binaryTreeInorder.py` 等。

## 开发约定

- 可视化脚本面向 **Script Editor**，入口使用 `asyncio.ensure_future(main())`，不必写 `if __name__ == "__main__"`
- 终端输出使用英文，避免乱码
- 坐标系遵循 Isaac Sim 默认 **Z-up**
- 优先使用 `isaacsim.core.experimental`（`Cube`、`GroundPlane`、`stage_utils`、`app_utils` 等）

## Git

```bash
git clone <your-repo-url>
cd IsaacLeetViz
```

本地若尚未初始化：

```bash
git init
git add .
git commit -m "Initial commit: IsaacLeetViz with Number of Islands viz"
```

## License

MIT（可按需要自行更换）
