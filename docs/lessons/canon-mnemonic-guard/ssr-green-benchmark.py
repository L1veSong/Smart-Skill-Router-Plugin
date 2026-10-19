"""
[DEPRECATED] SSR GREEN 基准测试 — 已迁移

此脚本已被三维评分系统替代:
    ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py

用法:
    python3 ssr_scoring_benchmark.py --mode total      # 全链路
    python3 ssr_scoring_benchmark.py --mode embedding  # embedding裸分
    python3 ssr_scoring_benchmark.py --mode gate       # 门控裸分
    python3 ssr_scoring_benchmark.py --mode all        # 三个一起

改进:
    - 零硬编码: 模型名从 config.yaml 读取
    - 50条基准 (30信号+20噪音) — 覆盖设计/调试/金融/旅行/学术/部署/PPT/地图/微信
    - 三维评分公式 (总分/embedding裸分/门控裸分)
    - JSON 输出 → Dashboard /api/scores 消费
    - v3 a_rules.json 格式兼容 (keywords 动态匹配)

旧脚本问题:
    - 硬编码 bge-m3 模型
    - 仅 5 条测试
    - 不兼容 v3 keywords 格式
    - 无噪音测试
"""

if __name__ == "__main__":
    import sys
    print(__doc__, file=sys.stderr)
    print("\n请使用新脚本:", file=sys.stderr)
    print("  python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode all", file=sys.stderr)
    sys.exit(1)
