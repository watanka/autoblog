#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NewsAPI를 활용한 뉴스 트렌드 파싱 모듈
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

class NewsAPIParser(TrendParser):
    """NewsAPI를 사용하여 최신 뉴스 트렌드를 파악하는 클래스"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        NewsAPI 파서를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): 설정 정보
        """
        self.logger = logging.getLogger('autoblog.trends.newsapi')
        
        # NewsAPI 설정
        self.api_key = os.environ.get('NEWSAPI_KEY')
        self.api_url = "https://newsapi.org/v2/top-headlines"
        
        # 검색 설정
        self.country = config.get('trends', {}).get('newsapi', {}).get('country', 'kr')
        self.page_size = config.get('trends', {}).get('newsapi', {}).get('page_size', 20)
        self.categories = config.get('trends', {}).get('newsapi', {}).get('categories', ['technology', 'business', 'science'])
        
        # 트렌드 파악 설정
        self.max_trends = config.get('trends', {}).get('max_trends', 10)
        
        # 키워드 필터링
        self.blacklist = config.get('trends', {}).get('analysis', {}).get('blacklist', [])
        
        # API 요청 제한 관리
        self.last_request_time = 0
        self.request_interval = 1.5  # 초 단위 (API 요청 제한 준수)
        
        # HTTP 세션 초기화
        self.session = requests.Session()
        
        if not self.api_key:
            self.logger.error("NewsAPI 키가 설정되지 않았습니다.")
    
    def get_trends(self, job_id: str = None) -> List[Dict[str, Any]]:
        """
        현재 인기 있는 뉴스 기사를 가져옵니다.
        
        Args:
            job_id (str, optional): 작업 ID
            
        Returns:
            List[Dict[str, Any]]: 파싱된 뉴스 기사 목록
        """
        if not self.api_key:
            self.logger.error("NewsAPI 키가 없어 뉴스를 가져올 수 없습니다.")
            return []
        
        # 성능 측정 시작
        if job_id:
            update_job_status(job_id, "in_progress")
            start_time = time.time()
        
        api_calls = 0  # API 호출 횟수 추적
        
        try:
            all_articles = []
            for category in self.categories:
                category_articles = self._fetch_top_headlines(category)
                all_articles.extend(category_articles)
                api_calls += 1
                self.logger.info(f"{category} 카테고리에서 {len(category_articles)}개 기사 가져옴")
            
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
    
    def _fetch_top_headlines(self, category: str) -> List[Dict[str, Any]]:
        """
        NewsAPI를 통해 특정 카테고리의 헤드라인 뉴스를 가져옵니다.
        
        Args:
            category (str): 뉴스 카테고리
            
        Returns:
            List[Dict[str, Any]]: 뉴스 기사 목록
        """
        # API 요청 제한 관리
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        
        params = {
            "apiKey": self.api_key,
            "country": self.country,
            "category": category,
            "pageSize": self.page_size
        }
        
        self.logger.debug(f"NewsAPI 호출: 카테고리={category}, 국가={self.country}")
        
        try:
            response = self.session.get(self.api_url, params=params)
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                self.logger.error(f"NewsAPI 오류: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            if data.get('status') != 'ok' or 'articles' not in data:
                self.logger.error(f"NewsAPI 응답에 'articles' 필드가 없거나 상태가 ok가 아닙니다: {data}")
                return []
            
            # 응답 데이터를 표준 형식으로 변환
            processed_articles = []
            for article in data['articles']:
                title = article.get('title', '')
                description = article.get('description', '')
                
                # 블랙리스트 키워드 체크
                if self._contains_blacklisted_terms(f"{title} {description}"):
                    continue
                
                # 기사 정보 저장
                processed = {
                    'title': title,
                    'description': description,
                    'content': article.get('content', description),
                    'url': article.get('url', ''),
                    'published_at': article.get('publishedAt', ''),
                    'source': {
                        'name': article.get('source', {}).get('name', ''),
                        'url': self._extract_publisher_domain(article.get('url', ''))
                    },
                    'category': category,
                    'image': article.get('urlToImage', ''),
                    'keywords': self._extract_keywords(f"{title} {description}")
                }
                processed_articles.append(processed)
            
            return processed_articles
            
        except requests.RequestException as e:
            self.logger.error(f"NewsAPI 요청 중 오류 발생: {str(e)}")
            return []
    
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
            # 1. 카테고리 가중치
            category_weight = 1.0
            if article.get('category') in ['technology', 'business']:
                category_weight = 1.2
            
            # 2. 이미지 유무 (이미지가 있으면 더 높은 점수)
            image_weight = 1.0
            if article.get('image'):
                image_weight = 1.1
            
            # 3. 콘텐츠 품질 (설명 길이 기반)
            description_length = len(article.get('description', ''))
            content_quality = min(1.0, description_length / 150)  # 150자 이상이면 최대 점수
            
            # 트렌드 점수 계산 (0-100)
            trend_score = 60 * category_weight * image_weight * content_quality
            
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
        # 특수문자 제거
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 단어 추출
        words = text.split()
        keywords = []
        
        # 키워드 선별 (영어/한국어 구분)
        if self.country == 'kr':
            # 한국어 키워드 (2글자 이상)
            for word in words:
                if len(word) >= 2 and re.match(r'[\uac00-\ud7a3]+', word):
                    keywords.append(word)
        else:
            # 영어 키워드 (4글자 이상)
            for word in words:
                if len(word) > 3:
                    keywords.append(word.lower())
        
        # 중복 제거 및 상위 10개 반환
        unique_keywords = list(set(keywords))
        return unique_keywords[:10]
