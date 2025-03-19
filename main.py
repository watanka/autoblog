#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
자동화 블로그 시스템 메인 실행 파일
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import Dict, Any
# 코어 모듈 임포트
from src.core.system import BlogAutomationSystem

# 트렌드 모듈 임포트
from src.core.interfaces import TrendParser
from src.trends.parsers import GNewsParser, NaverNewsParser, NewsAPIParser
from src.core.interfaces import TrendAnalyzer
from src.trends.analyzers.trend_analyzer import GNewsTrendAnalyzer

# 콘텐츠 모듈 임포트
from src.core.interfaces import ContentGenerator
from src.content.generators.openai import OpenAIContentGenerator
from src.core.interfaces import ContentFormatter
from src.content.formatters.docusaurus import DocusaurusFormatter

# 게시 모듈 임포트
from src.core.interfaces import Publisher
from src.publishing.platforms.docusaurus import DocusaurusPublisher


# 유틸리티 모듈 임포트
from src.utils.config import ConfigLoader
from src.utils.logger import setup_logger
from dotenv import load_dotenv

load_dotenv()

def parse_arguments():
    parser = argparse.ArgumentParser(description='수익형 블로그 자동화 시스템')
    parser.add_argument('--config', type=str, default='config/default.yml', 
                        help='설정 파일 경로')
    parser.add_argument('--mode', type=str, choices=['full', 'trends', 'content', 'publish'],
                        default='full', help='실행 모드')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='로깅 레벨')
    parser.add_argument('--job-id', type=str, help='특정 작업 ID의 데이터를 사용할 경우 지정')
    return parser.parse_args()


def create_parser(parser_type: str, config: Dict[str, Any]):
    """
    파서 타입에 따라 적절한 파서 인스턴스를 생성합니다.
    """
    logger = logging.getLogger('autoblog.main')
    
    if parser_type == 'gnews':
        logger.info("GNews 트렌드 파서 생성")
        return GNewsParser(config)
    elif parser_type == 'naver':
        logger.info("네이버 뉴스 트렌드 파서 생성")
        return NaverNewsParser(config)
    elif parser_type == 'newsapi':
        logger.info("NewsAPI 트렌드 파서 생성")
        return NewsAPIParser(config)
    else:
        logger.error(f"지원하지 않는 파서 유형: {parser_type}")
        return None



def main():
    args = parse_arguments()
    
    logger = setup_logger(log_level=args.log_level)
    logger.info(f"블로그 자동화 시스템 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        config = ConfigLoader.load(args.config)
        logger.info(f"설정 로드 완료: {args.config}")
    except Exception as e:
        logger.error(f"설정 로드 실패: {e}")
        sys.exit(1)
    
    try:
        # 뉴스 기사 파서 초기화
        parser_types = config.get('trends', {}).get('sources', [])
        trend_parsers = [create_parser(parser_type, config) for parser_type in parser_types]
        
        # 뉴스 기사 분석기 초기화
        trend_analyzer = GNewsTrendAnalyzer(config)
        
        # 콘텐츠 생성기 초기화
        content_generator = OpenAIContentGenerator(config)
        
        # 마크다운 포맷터 초기화
        content_formatter = DocusaurusFormatter(
            templates=config['content']['templates']
        )
        
        # 게시 플랫폼 초기화
        publisher = DocusaurusPublisher(
            config=config
        )
        
        logger.info("모든 모듈 초기화 완료")
        
    except Exception as e:
        logger.error(f"모듈 초기화 실패: {e}")
        sys.exit(1)
    
    # 5. 시스템 구성
    try:
        blog_system = BlogAutomationSystem(
            trend_parsers=trend_parsers,
            trend_analyzer=trend_analyzer,
            content_generator=content_generator,
            content_formatter=content_formatter,
            publishers={
                'docusaurus': publisher
            },
            config=config['system']
        )
        
        logger.info("시스템 구성 완료")
        
    except Exception as e:
        logger.error(f"시스템 구성 실패: {e}")
        sys.exit(1)
    
    # 6. 모드에 따른 실행
    try:
        if args.mode == 'full' or args.mode == 'trends':
            # 뉴스 기사 수집 실행
            articles = blog_system.discover_trends()
            logger.info(f"뉴스 기사 수집 완료: {len(articles)}개 기사 수집됨")
            
            # 뉴스 기사 분석 실행
            analyzed_articles = blog_system.analyze_trends(articles)
            if analyzed_articles:
                logger.info(f"뉴스 기사 분석 완료: 상위 수익성 기사: '{analyzed_articles[0]['title']}'")
            else:
                logger.info("뉴스 기사 분석 완료: 분석된 기사 없음")
            
            # 데이터 저장
            trends_path = blog_system.save_trends_data(analyzed_articles)
            logger.info(f"뉴스 기사 데이터 저장 완료: {trends_path}")
            
            # 현재 작업 ID 출력
            current_job_id = blog_system.job_id
            logger.info(f"현재 작업 ID: {current_job_id}")
        
        if args.mode == 'full' or args.mode == 'content':
            # 컨텐츠 생성
            if args.mode != 'full':
                # 별도 실행 시 저장된 뉴스 기사 로드
                analyzed_articles = blog_system.load_trends_data(job_id=args.job_id)
                if not analyzed_articles:
                    logger.error("뉴스 기사 데이터 로드 실패")
                    sys.exit(1)
            
            contents = blog_system.generate_contents(analyzed_articles)
            logger.info(f"콘텐츠 생성 완료: {len(contents)}개 포스트 생성됨")
            
            # 데이터 저장
            contents_path = blog_system.save_contents_data(contents)
            logger.info(f"콘텐츠 데이터 저장 완료: {contents_path}")
        
        if args.mode == 'full' or args.mode == 'publish':
            # 포스트 게시
            if args.mode != 'full':
                # 별도 실행 시 저장된 콘텐츠 로드
                contents = blog_system.load_contents_data(job_id=args.job_id)
                if not contents:
                    logger.error("콘텐츠 데이터 로드 실패")
                    sys.exit(1)
            
            publishing_results = blog_system.publish_contents(contents)
            logger.info(f"포스트 게시 완료: {len(publishing_results)}개 포스트 게시됨")
        
            results_path = blog_system.save_publishing_results(publishing_results)
            logger.info(f"게시 결과 저장 완료: {results_path}")
        
        # 작업 완료 - 작업 ID를 출력하여 사용자가 참조할 수 있게 함
        if blog_system.job_id:
            logger.info(f"작업 ID '{blog_system.job_id}'로 모든 작업이 완료되었습니다.")
            print(f"작업 ID: {blog_system.job_id}")
        
        logger.info(f"블로그 자동화 시스템 실행 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return 0
        
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
