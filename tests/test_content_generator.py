#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenAI 콘텐츠 생성기 테스트 스크립트
"""

import os
import sys
import json
import logging
from datetime import datetime

# 모듈 임포트를 위한 경로 추가 - 상위 디렉토리(프로젝트 루트)를 추가합니다.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.config import ConfigLoader
from src.trends.parsers.gnews_parser import GNewsParser
from src.trends.analyzers.trend_analyzer import GNewsTrendAnalyzer
from src.content.generators.openai import OpenAIContentGenerator
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def setup_logging():
    """로깅 설정을 초기화합니다."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'content_generator_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # 루트 로거 설정
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 포맷 설정
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def save_content(content, output_dir='../test_data/contents'):
    """생성된 콘텐츠를 파일로 저장합니다."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON 파일로 저장
    json_file = os.path.join(output_dir, f'content_{timestamp}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    
    # 마크다운 파일로 저장
    md_file = os.path.join(output_dir, f'content_{timestamp}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(f"# {content.get('title', '제목 없음')}\n\n")
        f.write(content.get('content', ''))
    
    return json_file, md_file

def main():
    """
    콘텐츠 생성기 테스트 스크립트의 메인 함수
    """
    # 로깅 설정
    logger = setup_logging()
    logger.info("=== 콘텐츠 생성기 테스트 시작 ===")
    
    # 설정 로드
    config = ConfigLoader().load('../config/default.yml')
    logger.info("설정 로드 완료")
    
    try:
        # 1. 뉴스 기사 가져오기
        logger.info("1. 뉴스 기사 수집 시작")
        parser = GNewsParser(config)
        articles = parser.get_trends()
        logger.info(f"   {len(articles)}개 뉴스 기사 수집 완료")
        
        if not articles:
            logger.error("수집된 뉴스 기사가 없습니다. 프로세스를 종료합니다.")
            return
        
        # 2. 뉴스 기사 분석
        logger.info("2. 뉴스 기사 분석 시작")
        analyzer = GNewsTrendAnalyzer(config)
        analyzed_articles = analyzer.analyze_trends(articles)
        logger.info(f"   {len(analyzed_articles)}개 뉴스 기사 분석 완료")
        
        if not analyzed_articles:
            logger.error("분석된 뉴스 기사가 없습니다. 프로세스를 종료합니다.")
            return
        
        # 상위 기사 선택
        test_article = analyzed_articles[0]
        logger.info(f"테스트 기사: '{test_article['title']}'")
        
        # 3. 콘텐츠 생성기 초기화
        logger.info("3. 콘텐츠 생성기 초기화")
        generator = OpenAIContentGenerator(config)
        logger.info("   콘텐츠 생성기 초기화 완료")
        
        # 비용 추정
        estimated_cost = generator.estimate_cost(test_article)
        logger.info(f"   예상 비용: ${estimated_cost:.4f}")
        
        # 4. 콘텐츠 생성
        logger.info("4. 콘텐츠 생성 시작")
        content = generator.generate_content(test_article)
        logger.info("   콘텐츠 생성 완료")
        
        # 생성된 콘텐츠 정보 출력
        print("\n=== 생성된 콘텐츠 ===")
        print(f"제목: {content.get('title', '제목 없음')}")
        print(f"원본 기사: {test_article.get('title', '')}")
        print(f"원본 출처: {test_article.get('source', {}).get('name', '')}")
        print(f"생성 모델: {content.get('generated_with', '')}")
        print("\n=== 콘텐츠 미리보기 ===")
        content_preview = content.get('content', '') + "..." if len(content.get('content', '')) > 2000 else content.get('content', '')
        print(content_preview)
        
        # 5. 콘텐츠 저장
        json_file, md_file = save_content(content)
        logger.info(f"5. 생성된 콘텐츠 저장 완료: {json_file}, {md_file}")
        
        logger.info("=== 콘텐츠 생성기 테스트 완료 ===")
    
    except Exception as e:
        logger.exception(f"오류 발생: {str(e)}")
        return

if __name__ == "__main__":
    main() 