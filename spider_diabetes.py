"""
糖尿病病例图片爬取脚本
目标：爬取1000张糖尿病相关的病例图片
"""
import os
import time
from loguru import logger
from main import Data_Spider
from xhs_utils.common_util import init

class DiabetesImageSpider:
    def __init__(self):
        self.data_spider = Data_Spider()
        self.cookies_str, self.base_path = init()
        
        # 创建专门的糖尿病图片目录
        self.diabetes_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), 'datas/diabetes_images'
        ))
        if not os.path.exists(self.diabetes_path):
            os.makedirs(self.diabetes_path)
            logger.info(f'创建糖尿病图片目录: {self.diabetes_path}')
        
        # 更新保存路径
        self.base_path['media'] = self.diabetes_path
        
        # 只搜索糖尿病病例
        self.keywords = [
            "糖尿病病例"
        ]
        
        # 不同的排序方式
        self.sort_types = [
            0,  # 综合排序
            1,  # 最新
            2,  # 最多点赞
        ]
        
        self.target_images = 1000
        self.collected_images = 0
        self.processed_notes = set()  # 记录已处理的笔记ID，避免重复
        
    def count_downloaded_images(self):
        """统计已下载的图片数量"""
        if not os.path.exists(self.diabetes_path):
            return 0
        
        image_count = 0
        for root, dirs, files in os.walk(self.diabetes_path):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    image_count += 1
        return image_count
    
    def search_and_download(self, keyword, sort_type, note_type=2):
        """
        搜索并下载图片
        :param keyword: 搜索关键词
        :param sort_type: 排序方式
        :param note_type: 笔记类型 2=普通笔记(图文)
        """
        try:
            # 每次搜索20个笔记
            query_num = 20
            
            logger.info(f'开始搜索关键词: {keyword}, 排序方式: {sort_type}, 笔记类型: 图文')
            
            note_list, success, msg = self.data_spider.spider_some_search_note(
                query=keyword,
                require_num=query_num,
                cookies_str=self.cookies_str,
                base_path=self.base_path,
                save_choice='media-image',  # 只下载图片
                sort_type_choice=sort_type,
                note_type=note_type,  # 2 = 普通笔记(图文)
                note_time=0,  # 不限时间
                note_range=0,  # 不限范围
                pos_distance=0,  # 不限位置
                geo=None,
                excel_name='',
                proxies=None
            )
            
            if success:
                logger.info(f'成功处理关键词 {keyword}，获取 {len(note_list)} 个笔记')
                # 记录已处理的笔记
                for note_url in note_list:
                    note_id = note_url.split('/explore/')[-1].split('?')[0]
                    self.processed_notes.add(note_id)
            else:
                logger.warning(f'搜索关键词 {keyword} 失败: {msg}')
            
            return success
            
        except Exception as e:
            logger.error(f'搜索关键词 {keyword} 时出错: {e}')
            return False
    
    def run(self):
        """执行爬取任务"""
        logger.info('='*60)
        logger.info('开始爬取糖尿病病例图片')
        logger.info(f'目标数量: {self.target_images} 张')
        logger.info('='*60)
        
        # 先统计已下载的图片
        self.collected_images = self.count_downloaded_images()
        logger.info(f'已存在图片数量: {self.collected_images} 张')
        
        if self.collected_images >= self.target_images:
            logger.info(f'已达到目标数量！无需继续爬取。')
            return
        
        round_num = 0
        
        # 循环搜索直到达到目标数量
        while self.collected_images < self.target_images:
            round_num += 1
            logger.info(f'\n--- 第 {round_num} 轮搜索 ---')
            
            for keyword in self.keywords:
                for sort_type in self.sort_types:
                    # 检查是否已达到目标
                    current_count = self.count_downloaded_images()
                    self.collected_images = current_count
                    
                    logger.info(f'当前进度: {self.collected_images}/{self.target_images} 张图片 ({self.collected_images/self.target_images*100:.1f}%)')
                    
                    if self.collected_images >= self.target_images:
                        logger.info(f'🎉 已完成目标！共收集 {self.collected_images} 张图片')
                        logger.info(f'图片保存路径: {self.diabetes_path}')
                        logger.info(f'共处理笔记数: {len(self.processed_notes)} 个')
                        return
                    
                    # 执行搜索和下载
                    success = self.search_and_download(keyword, sort_type)
                    
                    if success:
                        # 搜索成功后等待一小段时间，避免请求过快
                        time.sleep(2)
                    else:
                        # 失败则等待更长时间
                        logger.warning('搜索失败，等待5秒后继续...')
                        time.sleep(5)
            
            # 每轮结束后统计一次
            self.collected_images = self.count_downloaded_images()
            logger.info(f'第 {round_num} 轮完成，当前共收集: {self.collected_images} 张图片')
            
            # 如果多轮后仍未达到目标，可能需要调整策略
            if round_num >= 3 and self.collected_images < self.target_images:
                logger.warning(f'已进行 {round_num} 轮搜索，仍未达到目标。')
                logger.warning(f'可能的原因：关键词相关内容不足，或网络限制。')
                logger.info(f'当前已收集: {self.collected_images} 张图片')
                
                # 询问是否继续
                continue_choice = input('是否继续爬取？(y/n): ')
                if continue_choice.lower() != 'y':
                    logger.info(f'用户选择停止。最终收集: {self.collected_images} 张图片')
                    break
        
        # 最终统计
        final_count = self.count_downloaded_images()
        logger.info('='*60)
        logger.info('爬取任务完成！')
        logger.info(f'最终图片数量: {final_count} 张')
        logger.info(f'处理笔记总数: {len(self.processed_notes)} 个')
        logger.info(f'图片保存路径: {self.diabetes_path}')
        logger.info('='*60)


if __name__ == '__main__':
    spider = DiabetesImageSpider()
    spider.run()
