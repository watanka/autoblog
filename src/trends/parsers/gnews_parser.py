#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GNews API를 활용한 뉴스 트렌드 파싱 모듈
"""

import logging
import requests
import time
from typing import List, Dict, Any, Optional
from collections import Counter
from datetime import datetime, timedelta
import re
import os
from urllib.parse import quote

from src.core.interfaces import TrendParser
from src.utils.metadata_enhancer import track_performance, track_api_usage, update_job_status

class GNewsParser(TrendParser):
    """GNews API를 사용하여 최신 뉴스에서 트렌드를 파악하는 클래스"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        GNews 뉴스 파서를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): 설정 정보
        """
        self.logger = logging.getLogger('autoblog.trends.gnews')
        
        # GNews API 설정
        self.api_key = os.environ.get('GNEWS_API_KEY')
        self.api_base_url = "https://gnews.io/api/v4"
        
        # 검색 설정
        self.language = config.get('trends', {}).get('gnews', {}).get('language', 'ko')
        self.country = config.get('trends', {}).get('gnews', {}).get('country', 'kr')
        self.max_results = config.get('trends', {}).get('gnews', {}).get('max_results', 10)
        self.categories = config.get('trends', {}).get('gnews', {}).get('categories', ['general', 'technology', 'business', 'entertainment', 'health'])
        
        # 트렌드 파악 설정
        self.max_trends = config.get('trends', {}).get('max_trends', 10)
        self.time_window_hours = config.get('trends', {}).get('time_window_hours', 24)
        
        # 키워드 필터링
        self.blacklist = config.get('trends', {}).get('analysis', {}).get('blacklist', [])
        
        # API 요청 제한 관리
        self.last_request_time = 0
        self.request_interval = 1.1  # 초 단위 (API 요청 간격)
        
        # HTTP 세션 초기화
        self.session = requests.Session()
        
        # 설정 로그 출력
        self.logger.info(f"GNewsParser 초기화: language={self.language}, country={self.country}")
        self.logger.info(f"카테고리: {', '.join(self.categories)}")
        
        if not self.api_key:
            self.logger.error("GNews API 키가 설정되지 않았습니다.")
    
    def get_trends(self, job_id=None) -> List[Dict[str, Any]]:
        """
        현재 인기 있는 뉴스 기사를 가져옵니다.
        
        Args:
            job_id (str, optional): 작업 ID
            
        Returns:
            List[Dict[str, Any]]: 파싱된 뉴스 기사 목록
        """
        if not self.api_key:
            self.logger.error("GNews API 키가 없어 뉴스를 가져올 수 없습니다.")
            return []
        
        # 작업 추적 및 성능 측정 시작
        if job_id:
            update_job_status(job_id, "in_progress")
            start_time = time.time()
        
        api_calls = 0  # API 호출 횟수 추적
        
        try:
            # 최근 기사 가져오기
            all_articles = []
            for category in self.categories:
                category_articles = self._fetch_top_news(category)
                all_articles.extend(category_articles)
                api_calls += 1  # 카테고리마다 API 호출 1회
                self.logger.info(f"{category} 카테고리에서 {len(category_articles)}개 기사 가져옴")
            
            self.logger.info(f"총 {len(all_articles)}개 기사 가져옴")
            
            if not all_articles:
                self.logger.warning("가져온 기사가 없습니다.")
                # 작업 추적 종료
                if job_id:
                    end_time = time.time()
                    track_performance(job_id, "trend_analysis", start_time, end_time)
                    track_api_usage(job_id, "news", requests_made=api_calls)
                    update_job_status(job_id, "success")
                return []
            
            # 중복 제거 및 기사 필터링
            filtered_articles = self._filter_and_deduplicate_articles(all_articles)
            self.logger.info(f"필터링 후 {len(filtered_articles)}개 기사 남음")
            
            # 주요 정보 추출 및 정렬
            trending_articles = self._extract_trending_articles(filtered_articles)
            self.logger.info(f"트렌드 기사 {len(trending_articles)}개 선정됨")
            
            # 작업 추적 종료
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
                track_api_usage(job_id, "news", requests_made=api_calls)
                update_job_status(job_id, "success")
            
            return trending_articles[:self.max_trends]
            
        except Exception as e:
            self.logger.error(f"뉴스 가져오기 중 오류 발생: {str(e)}")
            
            # 오류 발생 시에도 작업 추적
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
                track_api_usage(job_id, "news", requests_made=api_calls)
                update_job_status(job_id, "failed", str(e))
            
            return []
    
    def _fetch_top_news(self, category: str) -> List[Dict[str, Any]]:
        """
        GNews API를 통해 특정 카테고리의 최신 뉴스를 가져옵니다.
        
        Args:
            category (str): 뉴스 카테고리
            
        Returns:
            List[Dict[str, Any]]: 최신 뉴스 기사 목록
        """
        # API 요청 제한 관리 (요청 간격 유지)
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        
        # 시간 범위 설정 (최근 n시간)
        from_date = (datetime.now() - timedelta(hours=self.time_window_hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        endpoint = f"{self.api_base_url}/top-headlines"
        params = {
            'token': self.api_key,
            'lang': self.language,
            'country': self.country,
            'topic': category,
            'max': self.max_results,
            'from': from_date
        }
        
        self.logger.debug(f"GNews API 호출: 카테고리={category}, 언어={self.language}, 국가={self.country}")
        
        try:
            response = self.session.get(endpoint, params=params)
            self.last_request_time = time.time()
            
            if response.status_code != 200:
                self.logger.error(f"GNews API 오류: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            
            if 'articles' not in data:
                self.logger.error(f"GNews API 응답에 'articles' 필드가 없습니다: {data}")
                return []
            
            # 필요한 정보만 추출하여 저장
            processed_articles = []
            for article in data['articles']:
                # 블랙리스트 키워드 체크
                title = article.get('title', '')
                description = article.get('description', '')
                content = article.get('content', '')
                
                if self._contains_blacklisted_terms(f"{title} {description} {content}"):
                    continue
                
                # 기사 정보 저장
                processed = {
                    'title': title,
                    'description': description,
                    'content': content,
                    'url': article.get('url', ''),
                    'published_at': article.get('publishedAt', ''),
                    'source': {
                        'name': article.get('source', {}).get('name', ''),
                        'url': article.get('source', {}).get('url', '')
                    },
                    'category': category,
                    'image': article.get('image', ''),
                    'keywords': self._extract_keywords(f"{title} {description}")
                }
                processed_articles.append(processed)
            
            return processed_articles
            
        except requests.RequestException as e:
            self.logger.error(f"GNews API 요청 중 오류 발생: {str(e)}")
            return []
    
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
            # 1. 카테고리 가중치 (일부 카테고리는 더 중요할 수 있음)
            category_weight = 1.0
            if article.get('category') in ['technology', 'business']:
                category_weight = 1.2
            
            # 2. 소스 신뢰도 (향후 확장 가능)
            source_weight = 1.0
            
            # 3. 콘텐츠 품질 (설명 길이 기반)
            description_length = len(article.get('description', ''))
            content_quality = min(1.0, description_length / 200)  # 200자 이상이면 최대 점수
            
            # 트렌드 점수 계산 (0-100)
            trend_score = 60 * category_weight * source_weight * content_quality

            
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
        텍스트에서 키워드를 추출합니다. (부가 정보용)
        
        Args:
            text (str): 키워드를 추출할 텍스트
            
        Returns:
            List[str]: 추출된 키워드 목록
        """
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # 특수문자 제거
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 소문자 변환 (영어의 경우)
        if self.language != 'ko':
            text = text.lower()
        
        # 단어 추출
        words = text.split()
        keywords = []
        
        # 한국어 처리 조건
        if self.language == 'ko':
            # 2글자 이상 키워드 (한글)
            for word in words:
                if len(word) >= 2 and re.match(r'[\uac00-\ud7a3]+', word):
                    keywords.append(word)
            
            # 복합 키워드 (2단어)
            for i in range(len(words) - 1):
                if len(words[i]) >= 2 and len(words[i+1]) >= 2:
                    compound = f"{words[i]} {words[i+1]}"
                    keywords.append(compound)
        else:
            # 영어 등 비한국어 처리
            # 4글자 이상 키워드
            for word in words:
                if len(word) > 3:  # 4글자 이상만 키워드로 간주
                    keywords.append(word)
            
            # 복합 키워드 (2단어)
            for i in range(len(words) - 1):
                if len(words[i]) > 2 and len(words[i+1]) > 2:
                    compound = f"{words[i]} {words[i+1]}"
                    keywords.append(compound)
        
        # 중복 제거 및 상위 10개 반환
        unique_keywords = list(set(keywords))
        return unique_keywords[:10]