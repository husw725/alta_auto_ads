"""测试脚本 - 为特定剧集查找视频"""
from core.video_selector import AutoMetaADS

selector = AutoMetaADS()

# 处理你的请求
success, result = selector.process_request(
    "我要投 the CEO and the country girl 到美国",
    enable_campaign=False
)

if success:
    print("\n" + "=" * 60)
    print("✅ 成功找到视频!")
    print("=" * 60)
    print(f"📁 剧集：{result['drama']}")
    print(f"🗣️ 语言：{result['language']}")
    print(f"👨‍🎨 设计师：{result['designer']}")
    print(f"📅 日期：{result['date']}")
    print(f"🎬 视频：{result['video']}")
    print(f"🔗 视频链接：{result['video_link']}")
    print("=" * 60)
else:
    print(f"\n❌ 错误：{result}")