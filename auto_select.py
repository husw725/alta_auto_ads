"""
Auto Meta ADS - 主程序
整合视频选择和 Campaign 创建的完整流程
"""

from core.video_selector import AutoMetaADS
from core.campaign_manager import CampaignManager


class AutoMetaADSSolution:
    """完整的自动投流解决方案"""
    
    def __init__(self):
        self.selector = AutoMetaADS()
        self.campaign_manager = CampaignManager()
    
    def process_request(self, user_input, enable_campaign=True):
        """
        处理用户请求
        
        Args:
            user_input: 自然语言输入
            enable_campaign: 是否自动创建 Campaign
        
        Returns:
            success, result
        """
        # Step 1: 选择视频
        success, result = self.selector.process_request(user_input, enable_campaign=False)
        
        if not success:
            return False, result
        
        # Step 2: 创建 Campaign（如果启用）
        if enable_campaign and result['video_link']:
            print("\n" + "=" * 60)
            print("🚀 创建 Campaign")
            print("=" * 60)
            
            campaign_result = self.campaign_manager.create_campaign(
                drama_name=result['drama'],
                video_url=result['video_link'],
                designer_name=result.get('designer', 'Auto'),
                country=result['language']
            )
            
            result['campaign'] = campaign_result
        
        return True, result


def main():
    """主函数"""
    solution = AutoMetaADSSolution()
    
    # 测试用例
    test_inputs = [
        "我要投 the CEO and the country girl 到美国",
        "我要投 FFAS 这部剧 到美国地区",
        "我要投卸甲后我名动京城这部剧",
        "卸甲后我名动京城的德语视频",
    ]
    
    for user_input in test_inputs:
        success, result = solution.process_request(
            user_input, 
            enable_campaign=False  # 默认为 false，避免 API 调用
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
            print(f"🔗 视频链接：{result['video_link'][:60]}...")
            print("=" * 60)
        else:
            print(f"\n❌ 错误：{result}")
            print("=" * 60)
        
        print("\n" + "-" * 60 + "\n")
        
        if isinstance(result, str) and "❓" in result:
            print("需要用户确认，中断测试")
            break


if __name__ == '__main__':
    main()