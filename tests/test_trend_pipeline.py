#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
뉴스 기사 파싱 및 분석 파이프라인 테스트 스크립트
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
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
def setup_logging():
    """로깅 설정을 초기화합니다."""
    log_dir = os.path.join(os.path.dirname(__file__), 'test_data/logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'article_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
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



def save_results(trending_articles, analyzed_articles):
    """결과를 JSON 파일로 저장합니다."""
    output_dir = os.path.join(os.path.dirname(__file__), '../data')
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 원본 트렌드 저장
    raw_file = os.path.join(output_dir, f'raw_articles_{timestamp}.json')
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump(trending_articles, f, ensure_ascii=False, indent=2)
    
    # 분석된 트렌드 저장
    analyzed_file = os.path.join(output_dir, f'analyzed_articles_{timestamp}.json')
    with open(analyzed_file, 'w', encoding='utf-8') as f:
        json.dump(analyzed_articles, f, ensure_ascii=False, indent=2)
    
    return raw_file, analyzed_file


def display_article(article, index=None, detailed=False):
    """기사 정보를 화면에 표시합니다."""
    prefix = f"{index}. " if index is not None else ""
    
    print(f"\n{prefix}제목: {article.get('title', '')}")
    print(f"   출처: {article.get('source', {}).get('name', '')}")
    print(f"   카테고리: {article.get('category', '')}")
    
    if detailed:
        print(f"   설명: {article.get('description', '')}")
        print(f"   URL: {article.get('url', '')}")
        print(f"   발행일: {article.get('published_at', '')}")
        if 'trend_score' in article:
            print(f"   트렌드 점수: {article.get('trend_score', 0):.1f}")
    
    # 분석 결과 표시
    if 'popularity_score' in article:
        print(f"   인기도 점수: {article.get('popularity_score', 0):.1f}")
        print(f"   수익 잠재력: {article.get('revenue_potential', '')}")
        print(f"   추정 카테고리: {', '.join(article.get('estimated_categories', []))}")
        print(f"   추천 태그: {', '.join(article.get('recommended_tags', []))}")
        
        # 블로그 주제 제안 표시
        if 'blog_topic' in article:
            print(f"   블로그 주제: {article.get('blog_topic', '')}")


def main():
    """
    뉴스 기사 파싱 및 분석 파이프라인 테스트 스크립트의 메인 함수
    """
    # 로깅 설정
    logger = setup_logging()
    logger.info("=== 뉴스 기사 파이프라인 테스트 시작 ===")
    
    # 설정 로드
    config = ConfigLoader().load('config/default.yml')
    logger.info("설정 로드 완료")
    
    try:
        # 1. 뉴스 기사 수집
        logger.info("1. 뉴스 기사 수집 시작")
        parser = GNewsParser(config)
        trending_articles = parser.get_trends()
        logger.info(f"   {len(trending_articles)}개 뉴스 기사 수집 완료")
        
        if not trending_articles:
            logger.error("수집된 뉴스 기사가 없습니다. 프로세스를 종료합니다.")
            return
        
        # 수집된 뉴스 기사 간략 정보 출력
        print("\n=== 수집된 뉴스 기사 ===")
        for i, article in enumerate(trending_articles, 1):
            display_article(article, i)
        
        # 2. 뉴스 기사 분석
        logger.info("2. 뉴스 기사 분석 시작")
        analyzer = GNewsTrendAnalyzer(config)
        analyzed_articles = analyzer.analyze_trends(trending_articles)
        logger.info(f"   {len(analyzed_articles)}개 뉴스 기사 분석 완료")
        
        if not analyzed_articles:
            logger.error("분석된 뉴스 기사가 없습니다. 프로세스를 종료합니다.")
            return
        
        # 분석된 뉴스 기사 정보 출력
        print("\n=== 분석된 뉴스 기사 ===")
        for i, article in enumerate(analyzed_articles, 1):
            display_article(article, i, detailed=True)
            
            # 기사 요약 표시
            if 'summary' in article:
                print("\n   [요약]")
                print(f"   {article['summary'].replace('\n', '\n   ')}")
            
            # 구분선 추가
            print("\n" + "-" * 80)
        
        # 3. 결과 저장
        raw_file, analyzed_file = save_results(trending_articles, analyzed_articles)
        logger.info(f"3. 결과 저장 완료: {raw_file}, {analyzed_file}")
        
        # 4. OpenAI API 요청에 사용할 수 있는 데이터 구조 예시
        print("\n=== OpenAI API 요청 데이터 형식 예시 ===")
        if analyzed_articles:
            example_article = analyzed_articles[0]
            
            openai_prompt = {
                "messages": [
                    {"role": "system", "content": "당신은 전문적인 블로그 작가입니다. 제공된 뉴스 기사를 바탕으로 흥미로운 블로그 게시물을 작성해주세요."},
                    {"role": "user", "content": f"""
다음 뉴스 기사를 바탕으로 블로그 게시물을 작성해주세요:

제목: {example_article.get('title', '')}
설명: {example_article.get('description', '')}
카테고리: {', '.join(example_article.get('estimated_categories', []))}
추천 태그: {', '.join(example_article.get('recommended_tags', []))}
블로그 주제: {example_article.get('blog_topic', '')}

블로그 글은 다음 구조로 작성해주세요:
1. 제목: 독자의 호기심을 자극하면서 핵심 내용을 담은 매력적인 제목
2. 도입부: 독자의 관심을 끌 수 있는 흥미로운 시작
3. 본론: 주요 내용을 2-3개의 소제목으로 나누어 설명
4. 결론: 핵심 내용 요약 및 독자에게 생각할 거리 제공
5. 행동 유도: 독자가 다음으로 취할 수 있는 구체적인 행동 제안

마크다운 형식으로 작성해주세요.
"""}
                ]
            }
            
            print(json.dumps(openai_prompt, ensure_ascii=False, indent=2))
        
        logger.info("=== 뉴스 기사 파이프라인 테스트 완료 ===")
    
    except Exception as e:
        logger.exception(f"오류 발생: {str(e)}")
        return


if __name__ == "__main__":
    main() 