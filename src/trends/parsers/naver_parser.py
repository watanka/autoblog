#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
네이버 뉴스 API를 활용한 뉴스 트렌드 파싱 모듈
"""

import logging
import requests
import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

from src.core.interfaces import TrendParser
from src.utils.metadata_enhancer import track_performance, track_api_usage, update_job_status

class NaverNewsParser(TrendParser):
    """네이버 뉴스 API를 사용하여 최신 뉴스 트렌드를 파악하는 클래스"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        네이버 뉴스 파서를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): 설정 정보
        """
        self.logger = logging.getLogger('autoblog.trends.naver')
        
        # 네이버 API 설정
        self.client_id = os.environ.get('NAVER_CLIENT_ID')
        self.client_secret = os.environ.get('NAVER_CLIENT_SECRET')
        self.api_url = "https://openapi.naver.com/v1/search/news.json"
        
        # 검색 설정
        self.display = config.get('trends', {}).get('naver', {}).get('display', 20)  # 한 번에 표시할 검색 결과 수
        self.start = config.get('trends', {}).get('naver', {}).get('start', 1)  # 검색 시작 위치
        self.sort = config.get('trends', {}).get('naver', {}).get('sort', 'date')  # 정렬 옵션 (sim: 정확도순, date: 날짜순)
        
        # 트렌드 파악 설정
        self.max_trends = config.get('trends', {}).get('max_trends', 10)
        self.time_window_hours = config.get('trends', {}).get('time_window_hours', 24)
        
        # 키워드 필터링
        self.blacklist = config.get('trends', {}).get('analysis', {}).get('blacklist', [])
        
        # API 요청 제한 관리
        self.last_request_time = 0
        self.request_interval = 0.3  # 초 단위 (네이버 API 요청 제한 준수)
        
        # HTTP 세션 초기화
        self.session = requests.Session()
        
        if not self.client_id or not self.client_secret:
            self.logger.error("네이버 API 인증 정보가 설정되지 않았습니다.")
    
    def get_trends(self, job_id: str = None) -> List[Dict[str, Any]]:
        """
        현재 인기 있는 뉴스 기사를 가져옵니다.
        
        Args:
            job_id (str, optional): 작업 ID
            
        Returns:
            List[Dict[str, Any]]: 파싱된 뉴스 기사 목록
        """
        if not self.client_id or not self.client_secret:
            self.logger.error("네이버 API 인증 정보가 없어 뉴스를 가져올 수 없습니다.")
            return []
        
        # 성능 측정 시작
        if job_id:
            update_job_status(job_id, "in_progress")
            start_time = time.time()
        
        api_calls = 0  # API 호출 횟수 추적
        
        try:
            # 인기 키워드 목록 (여기서는 예시로 몇 가지 키워드 사용)
            popular_keywords = ["AI", "인공지능", "빅데이터", "클라우드", "메타버스", "블록체인"]
            
            all_articles = []
            for keyword in popular_keywords:
                keyword_articles = self._fetch_news(keyword)
                all_articles.extend(keyword_articles)
                api_calls += 1
                self.logger.info(f"키워드 '{keyword}'에서 {len(keyword_articles)}개 기사 가져옴")
            
            self.logger.info(f"총 {len(all_articles)}개 기사 가져옴")
            
            if not all_articles:
                self.logger.warning("가져온 기사가 없습니다.")
                # 성능 추적 종료
                if job_id:
                    end_time = time.time()
                    track_performance(job_id, "trend_analysis", start_time, end_time)
                    track_api_usage(job_id, "news", requests_made=api_calls)
                    update_job_status(job_id, "success")
                return []
            
            # 중복 제거 및 기사 필터링
            filtered_articles = self._filter_and_deduplicate_articles(all_articles)
            self.logger.info(f"필터링 후 {len(filtered_articles)}개 기사 남음")
            
            # 트렌드 점수 계산 및 정렬
            trending_articles = self._extract_trending_articles(filtered_articles)
            self.logger.info(f"트렌드 기사 {len(trending_articles)}개 선정됨")
            
            # 성능 추적 종료
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
                track_api_usage(job_id, "news", requests_made=api_calls)
                update_job_status(job_id, "success")
            
            return trending_articles[:self.max_trends]
            
        except Exception as e:
            self.logger.error(f"뉴스 가져오기 중 오류 발생: {str(e)}")
            
            # 성능 추적 종료 (오류 상태)
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
                track_api_usage(job_id, "news", requests_made=api_calls)
                update_job_status(job_id, "failed", str(e))
            
            return []
    
    def _fetch_news(self, query: str) -> List[Dict[str, Any]]:
        """
        네이버 뉴스 API를 통해 특정 키워드에 대한 뉴스를 가져옵니다.
        
        Args:
            query (str): 검색 키워드
            
        Returns:
            List[Dict[str, Any]]: 뉴스 기사 목록
        """
        # API 요청 제한 관리
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        params = {
            "query": query,
            "display": self.display,
            "start": self.start,
            "sort": self.sort
        }
        
        self.logger.debug(f"네이버 뉴스 API 호출: 키워드='{query}'")
        
        try:
            response = self.session.get(self.api_url, params=params, headers=headers)
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                self.logger.error(f"네이버 API 오류: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            if 'items' not in data:
                self.logger.error(f"네이버 API 응답에 'items' 필드가 없습니다: {data}")
                return []
            
            # 응답 데이터를 표준 형식으로 변환
            processed_articles = []
            for item in data['items']:
                # HTML 태그 제거
                title = re.sub(r'<[^>]+>', '', item.get('title', ''))
                description = re.sub(r'<[^>]+>', '', item.get('description', ''))
                
                # 블랙리스트 키워드 체크
                if self._contains_blacklisted_terms(f"{title} {description}"):
                    continue
                
                # 기사 정보 저장
                processed = {
                    'title': title,
                    'description': description,
                    'content': description,  # 네이버 API는 전체 콘텐츠를 제공하지 않음
                    'url': item.get('link', ''),
                    'published_at': item.get('pubDate', ''),
                    'source': {
                        'name': self._extract_publisher_from_link(item.get('link', '')),
                        'url': self._extract_publisher_domain(item.get('link', ''))
                    },
                    'category': 'news',
                    'image': '',  # 네이버 API는 이미지 URL을 제공하지 않음
                    'keywords': self._extract_keywords(f"{title} {description}")
                }
                processed_articles.append(processed)
            
            return processed_articles
            
        except requests.RequestException as e:
            self.logger.error(f"네이버 API 요청 중 오류 발생: {str(e)}")
            return []
    
    def _extract_publisher_from_link(self, link: str) -> str:
        """링크에서 출판사 이름을 추출합니다."""
        if not link:
            return ''
        
        # 도메인 추출 (news.naver.com, n.news.naver.com 등)
        domain_match = re.search(r'https?://([^/]+)', link)
        if not domain_match:
            return ''
        
        domain = domain_match.group(1)
        
        # 출판사 매핑 (간단한 예시)
        publisher_mapping = {
            'news.naver.com': '네이버 뉴스',
            'n.news.naver.com': '네이버 뉴스',
            'news.joins.com': '중앙일보',
            'www.chosun.com': '조선일보',
            'news.sbs.co.kr': 'SBS 뉴스',
            'news.kbs.co.kr': 'KBS 뉴스',
            'news.imbc.com': 'MBC 뉴스',
            'www.yonhapnewstv.co.kr': '연합뉴스',
            'www.hani.co.kr': '한겨레',
            'www.khan.co.kr': '경향신문'
        }
        
        return publisher_mapping.get(domain, domain)
    
    def _extract_publisher_domain(self, link: str) -> str:
        """링크에서 출판사 도메인을 추출합니다."""
        if not link:
            return ''
        
        domain_match = re.search(r'https?://([^/]+)', link)
        if not domain_match:
            return ''
        
        return f"https://{domain_match.group(1)}"
    
    def _filter_and_deduplicate_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        기사 목록에서 중복을 제거하고 필터링합니다.
        
        Args:
            articles (List[Dict[str, Any]]): 필터링할 기사 목록
            
        Returns:
            List[Dict[str, Any]]: 필터링된 기사 목록
        """
        # URL 기준으로 중복 제거
        unique_articles = {}
        for article in articles:
            url = article.get('url', '')
            if url and url not in unique_articles:
                unique_articles[url] = article
        
        # 블랙리스트 필터링 다시 한번 수행
        filtered_articles = []
        for url, article in unique_articles.items():
            title = article.get('title', '')
            description = article.get('description', '')
            
            if not self._contains_blacklisted_terms(f"{title} {description}"):
                filtered_articles.append(article)
        
        return filtered_articles
    
    def _extract_trending_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        기사 목록에서 트렌드 기사를 추출합니다.
        
        Args:
            articles (List[Dict[str, Any]]): 분석할 기사 목록
            
        Returns:
            List[Dict[str, Any]]: 트렌드 기사 목록
        """
        # 게시 시간 기준으로 정렬 (최신순)
        sorted_articles = sorted(
            articles, 
            key=lambda x: x.get('published_at', ''),
            reverse=True
        )
        
        # 트렌드 점수 계산 (새로운 필드 추가)
        for article in sorted_articles:
            # 1. 소스 신뢰도 (향후 확장 가능)
            source_weight = 1.0
            source_name = article.get('source', {}).get('name', '')
            if source_name in ['네이버 뉴스', '중앙일보', '조선일보', 'KBS 뉴스', 'MBC 뉴스', 'SBS 뉴스', '연합뉴스']:
                source_weight = 1.2
            
            # 2. 콘텐츠 품질 (설명 길이 기반)
            description_length = len(article.get('description', ''))
            content_quality = min(1.0, description_length / 150)  # 150자 이상이면 최대 점수
            
            # 트렌드 점수 계산 (0-100)
            trend_score = 60 * source_weight * content_quality
            
            article['trend_score'] = min(100, trend_score)
        
        # 트렌드 점수로 정렬
        trending_articles = sorted(
            sorted_articles, 
            key=lambda x: x.get('trend_score', 0),
            reverse=True
        )
        
        return trending_articles
    
    def _contains_blacklisted_terms(self, text: str) -> bool:
        """
        텍스트에 블랙리스트 용어가 포함되어 있는지 확인합니다.
        
        Args:
            text (str): 확인할 텍스트
            
        Returns:
            bool: 블랙리스트 포함 여부
        """
        if not text:
            return False
            
        text_lower = text.lower()
        return any(term.lower() in text_lower for term in self.blacklist)

    def _extract_keywords(self, text: str) -> List[str]:
        """
        텍스트에서 키워드를 추출합니다.
        
        Args:
            text (str): 키워드를 추출할 텍스트
            
        Returns:
            List[str]: 추출된 키워드 목록
        """
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # 특수문자 제거
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 단어 추출
        words = text.split()
        keywords = []
        
        # 2글자 이상 키워드 (한글)
        for word in words:
            if len(word) >= 2 and re.match(r'[\uac00-\ud7a3]+', word):
                keywords.append(word)
        
        # 복합 키워드 (2단어)
        for i in range(len(words) - 1):
            if len(words[i]) >= 2 and len(words[i+1]) >= 2:
                compound = f"{words[i]} {words[i+1]}"
                keywords.append(compound)
        
        # 중복 제거 및 상위 10개 반환
        unique_keywords = list(set(keywords))
        return unique_keywords[:10]
