"""
糖尿病病例图片爬取脚本
目标：爬取糖尿病真实病例相关的图片
"""
import os
import time
from loguru import logger
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, download_note

class DiabetesImageSpider:
    def __init__(self):
        self.xhs_apis = XHS_Apis()
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
        
        # 使用更精确的关键词
        self.keywords = [
            "糖尿病病历",
            "糖尿病诊断书",
            "糖尿病检查报告",
            "糖尿病化验单"
        ]
        
        # 不同的排序方式
        self.sort_types = [
            0,  # 综合排序
            1,  # 最新
            2,  # 最多点赞
        ]
        
        # 内容过滤关键词 - 只保留明显的非病例内容黑名单
        self.blacklist = [
            "食谱", "吃什么", "食物",  # 纯饮食类
            "妙招", "攻略", "指南",     # 纯科普类
            "科普", "知识"              # 教育类
        ]
        
        self.target_images = 1000
        self.collected_images = 0
        self.processed_notes = set()  # 记录已处理的笔记ID，避免重复
        self.no_new_images_count = 0  # 连续没有新图片的计数
        self.max_no_new_rounds = 3  # 连续3轮没有新图片则停止
        
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
    
    def is_relevant_note(self, title, desc):
        """
        判断笔记是否相关（仅黑名单过滤）
        :param title: 笔记标题
        :param desc: 笔记描述
        :return: True表示相关，False表示不相关
        """
        content = (title + " " + desc).lower()
        
        # 检查黑名单
        for word in self.blacklist:
            if word in content:
                logger.debug(f'笔记包含黑名单关键词"{word}"，跳过: {title[:30]}')
                return False
        
        # 不在黑名单中就通过
        return True
    
    def search_and_download(self, keyword, sort_type, note_type=2):
        """
        搜索并下载图片（带内容过滤和限流检测）
        :param keyword: 搜索关键词
        :param sort_type: 排序方式
        :param note_type: 笔记类型 2=普通笔记(图文)
        """
        try:
            # 每次搜索10个笔记，减少API压力
            query_num = 10
            
            logger.info(f'开始搜索关键词: {keyword}, 排序方式: {sort_type}')
            
            # 调用API搜索
            success, msg, notes = self.xhs_apis.search_some_note(
                keyword, query_num, self.cookies_str, 
                sort_type, note_type, 0, 0, 0, None, None
            )
            
            if not success:
                logger.warning(f'搜索关键词 {keyword} 失败: {msg}')
                return False
            
            # 过滤笔记
            notes = list(filter(lambda x: x['model_type'] == "note", notes))
            logger.info(f'搜索到 {len(notes)} 个笔记')
            
            downloaded_count = 0
            filtered_count = 0
            rate_limited = False
            
            for note in notes:
                note_id = note['id']
                
                # 避免重复处理
                if note_id in self.processed_notes:
                    continue
                
                self.processed_notes.add(note_id)
                
                # 内容过滤
                title = note.get('title', '')
                desc = note.get('desc', '')
                
                if not self.is_relevant_note(title, desc):
                    filtered_count += 1
                    logger.info(f'跳过不相关笔记: {title[:30]}...')
                    continue
                
                # 构建笔记URL
                note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note.get('xsec_token', '')}"
                
                try:
                    success, msg, note_info = self.xhs_apis.get_note_info(
                        note_url, self.cookies_str, None
                    )
                    
                    # 检测限流
                    if '频次异常' in str(msg) or '频繁' in str(msg) or (note_info and note_info.get('code') == 300013):
                        logger.warning(f'⚠️ 触发频率限制，等待60秒...')
                        rate_limited = True
                        time.sleep(60)
                        continue
                    
                    # 检查响应是否有效
                    if not success or not note_info:
                        continue
                    
                    # 检查数据结构
                    if not note_info.get('data') or not note_info['data'].get('items') or len(note_info['data']['items']) == 0:
                        continue
                    
                    # 处理笔记信息
                    note_info = note_info['data']['items'][0]
                    note_info['url'] = note_url
                    note_info = handle_note_info(note_info)
                    
                    # 下载图片
                    download_note(note_info, self.base_path['media'], 'media-image')
                    downloaded_count += 1
                    logger.info(f'✅ 下载笔记: {title[:30]}...')
                    
                    # 下载后等待，避免触发限流
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f'处理笔记出错: {e}')
                    continue
            
            logger.info(f'本次搜索: 过滤 {filtered_count} 个, 下载 {downloaded_count} 个')
            
            # 如果触发了限流，返回False让主循环等待
            return not rate_limited
            
        except Exception as e:
            logger.error(f'搜索关键词 {keyword} 时出错: {e}')
            return False
    
    def run(self):
        """执行爬取任务"""
        logger.info('='*60)
        logger.info('开始爬取糖尿病真实病例图片')
        logger.info(f'目标数量: {self.target_images} 张（如内容不足将自动停止）')
        logger.info('='*60)
        
        # 先统计已下载的图片
        self.collected_images = self.count_downloaded_images()
        logger.info(f'已存在图片数量: {self.collected_images} 张')
        
        if self.collected_images >= self.target_images:
            logger.info(f'已达到目标数量！无需继续爬取。')
            return
        
        round_num = 0
        
        # 循环搜索直到达到目标数量或自动停止
        while self.collected_images < self.target_images:
            round_num += 1
            round_start_count = self.collected_images
            
            logger.info(f'\n--- 第 {round_num} 轮搜索 ---')
            
            for keyword in self.keywords:
                for sort_type in self.sort_types:
                    # 检查是否已达到目标
                    current_count = self.count_downloaded_images()
                    self.collected_images = current_count
                    
                    progress = (self.collected_images/self.target_images*100) if self.target_images > 0 else 0
                    logger.info(f'当前进度: {self.collected_images}/{self.target_images} 张图片 ({progress:.1f}%)')
                    
                    if self.collected_images >= self.target_images:
                        logger.info(f'🎉 已完成目标！共收集 {self.collected_images} 张图片')
                        logger.info(f'图片保存路径: {self.diabetes_path}')
                        logger.info(f'共处理笔记数: {len(self.processed_notes)} 个')
                        return
                    
                    # 执行搜索和下载
                    success = self.search_and_download(keyword, sort_type)
                    
                    if success:
                        # 搜索成功后等待，避免请求过快
                        time.sleep(3)
                    else:
                        # 失败或触发限流，等待更长时间
                        logger.warning('触发限流或搜索失败，等待10秒后继续...')
                        time.sleep(10)
            
            # 每轮结束后统计一次
            round_end_count = self.count_downloaded_images()
            self.collected_images = round_end_count
            new_images_this_round = round_end_count - round_start_count
            
            logger.info(f'第 {round_num} 轮完成，本轮新增: {new_images_this_round} 张，当前共: {self.collected_images} 张')
            
            # 检查是否有新图片下载
            if new_images_this_round == 0:
                self.no_new_images_count += 1
                logger.warning(f'本轮未下载到新图片 ({self.no_new_images_count}/{self.max_no_new_rounds})')
                
                if self.no_new_images_count >= self.max_no_new_rounds:
                    logger.info(f'⚠️ 连续 {self.max_no_new_rounds} 轮未获取新图片，自动停止')
                    logger.info(f'可能原因：相关内容已爬取完毕或过滤条件过于严格')
                    break
            else:
                # 有新图片则重置计数
                self.no_new_images_count = 0
        
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
