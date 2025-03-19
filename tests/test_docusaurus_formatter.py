#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docusaurus 포맷터 테스트 스크립트
"""

import os
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any

# 모듈 임포트를 위한 경로 추가 - 상위 디렉토리(프로젝트 루트)를 추가합니다.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 설정 로더 임포트
from src.utils.config import ConfigLoader

# Docusaurus 포맷터 임포트
from src.content.formatters.docusaurus import DocusaurusFormatter

def setup_logging():
    """로깅 설정을 초기화합니다."""
    # 로그 디렉토리 생성
    os.makedirs('logs', exist_ok=True)
    
    # 로거 설정
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(f'logs/formatter_test_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger()

def save_formatted_content(content: str, output_dir='../test_data/formatted'):
    """포맷팅된 콘텐츠를 파일로 저장합니다."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f'docusaurus_{timestamp}.md')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path

def load_sample_content(file_path: str) -> Dict[str, Any]:
    """샘플 콘텐츠를 JSON 파일에서 로드합니다."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Docusaurus 포맷터 테스트 스크립트의 메인 함수"""
    # 로깅 설정
    logger = setup_logging()
    logger.info("=== Docusaurus 포맷터 테스트 시작 ===")
    
    # 설정 로드
    config = ConfigLoader().load('../config/default.yml')
    logger.info("설정 로드 완료")
    
    try:
        # 1. 최신 생성 콘텐츠 찾기
        logger.info("1. 최신 생성 콘텐츠 찾기")
        content_dir = '../test_data/contents'
        
        if not os.path.exists(content_dir) or not os.listdir(content_dir):
            logger.error(f"콘텐츠 디렉토리가 비어있거나 존재하지 않습니다: {content_dir}")
            # 테스트 디렉토리 생성
            os.makedirs(content_dir, exist_ok=True)
            logger.info(f"테스트 디렉토리 생성: {content_dir}")
            
            # 샘플 콘텐츠 생성
            logger.info("샘플 콘텐츠 생성")
            sample_content = {
                "title": "스팀 덱에서 즐길 수 있는 최고의 게임, 봄 세일로 5달러 이하의 게임을 만나보세요!",
                "content": "# 스팀 덱에서 즐길 수 있는 최고의 게임, 봄 세일로 5달러 이하의 게임을 만나보세요!\n\n스팀의 봄 세일이 시작되었습니다! 여러분은 어떤 게임을 구매할 계획인가요?...",
                "article_data": {
                    "title": "Best Steam Deck games under $5 in the Spring Sale, up to 90% off",
                    "description": "Find great deals on Steam Deck games...",
                    "recommended_tags": ["gaming", "steam-deck", "sales", "budget-gaming"],
                    "estimated_categories": ["technology", "gaming"]
                },
                "generated_with": "gpt-4o-mini",
                "generated_at": datetime.now().isoformat()
            }
            
            # 샘플 콘텐츠 저장
            sample_file_path = os.path.join(content_dir, f"sample_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(sample_file_path, 'w', encoding='utf-8') as f:
                json.dump(sample_content, f, ensure_ascii=False, indent=2)
                
            logger.info(f"샘플 콘텐츠 저장 완료: {sample_file_path}")
            latest_file_path = sample_file_path
        else:
            # 최신 JSON 파일 찾기
            json_files = [f for f in os.listdir(content_dir) if f.endswith('.json')]
            if not json_files:
                logger.error("JSON 파일을 찾을 수 없습니다.")
                return
            
            latest_file = max(json_files, key=lambda x: os.path.getmtime(os.path.join(content_dir, x)))
            latest_file_path = os.path.join(content_dir, latest_file)
            
        logger.info(f"최신 콘텐츠 파일: {latest_file_path}")
        
        # 2. 콘텐츠 로드
        logger.info("2. 콘텐츠 로드")
        content = load_sample_content(latest_file_path)
        logger.info(f"콘텐츠 로드 완료: '{content.get('title', '제목 없음')}'")
        
        # 3. Docusaurus 포맷터 초기화
        logger.info("3. Docusaurus 포맷터 초기화")
        formatter = DocusaurusFormatter(
            templates=config['content']['templates']
        )
        logger.info("Docusaurus 포맷터 초기화 완료")
        
        # 4. 콘텐츠 포맷팅 - 기본 블로그 템플릿
        logger.info("4. 콘텐츠 포맷팅 - 블로그 템플릿")
        formatted_blog = formatter.format_content(content, 'blog')
        logger.info("블로그 템플릿 포맷팅 완료")
        
        # 포맷팅된 콘텐츠 저장
        blog_file = save_formatted_content(formatted_blog, '../test_data/formatted')
        logger.info(f"포맷팅된 Docusaurus 블로그 콘텐츠 저장 완료: {blog_file}")
        
        # 콘솔에 결과 출력
        print("\n=== 포맷팅된 Docusaurus 콘텐츠 ===")
        print(formatted_blog[:500] + "..." if len(formatted_blog) > 500 else formatted_blog)
        
        # 5. 기본 포맷팅 테스트
        logger.info("5. 기본 포맷팅 테스트")
        default_formatted = formatter._default_format(content)
        default_file = save_formatted_content(default_formatted, '../test_data/formatted')
        logger.info(f"기본 Docusaurus 포맷팅 완료: {default_file}")
        
        logger.info("=== Docusaurus 포맷터 테스트 완료 ===")
        
    except Exception as e:
        logger.exception(f"오류 발생: {str(e)}")
        return

if __name__ == "__main__":
    main() 