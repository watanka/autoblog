#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GNews 파서 테스트 스크립트
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
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def main():
    # 설정 로드
    config = ConfigLoader().load('../config/default.yml')
    
    # GNewsParser 인스턴스 생성
    parser = GNewsParser(config)
    
    # 뉴스 기사 가져오기
    print("뉴스 기사 가져오는 중...")
    articles = parser.get_trends()
    
    # 결과 출력
    print(f"총 {len(articles)}개 기사 발견")
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. 제목: {article['title']}")
        print(f"   설명: {article['description'][:100]}...")
        print(f"   URL: {article['url']}")
        print(f"   출처: {article['source']['name']}")
        
    # 결과 파일로 저장 (선택적)
    output_file = f"test_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n결과가 {output_file}에 저장되었습니다.")

if __name__ == "__main__":
    main()