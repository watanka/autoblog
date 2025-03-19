#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
수집된 트렌드를 분석하는 모듈
"""

import logging
import math
import re
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import Counter
import time

from src.core.interfaces import TrendAnalyzer
from src.utils.metadata_enhancer import update_job_metadata, track_performance, track_llm_usage, update_job_status

class GNewsTrendAnalyzer(TrendAnalyzer):
    """수집된 뉴스 기사를 분석하고 점수를 매기는 클래스"""

    def __init__(self, config: Dict[str, Any]):
        """
        트렌드 분석기를 초기화합니다.
        
        Args:
            config (Dict[str, Any]): 설정 정보
        """
        self.logger = logging.getLogger('autoblog.trends.analyzer')
        
        # 분석 설정
        analysis_config = config.get('trends', {}).get('analysis', {})
        self.popularity_threshold = analysis_config.get('popularity_threshold', 50)
        self.revenue_model = analysis_config.get('revenue_model', 'basic')
        self.blacklist = analysis_config.get('blacklist', [])
        self.max_results = analysis_config.get('max_results', 10)
        
        # 정의된 카테고리와 그에 해당하는 키워드
        self.categories = {
            'tech': ['기술', '인공지능', 'AI', '로봇', '자율주행', '블록체인', '암호화폐', '빅데이터', '클라우드', '사물인터넷', 'IoT', '5G', '가상현실', 'VR', '증강현실', 'AR'],
            'business': ['경제', '주식', '투자', '창업', '스타트업', '비즈니스', '마케팅', '금융', '부동산', '재테크', '세금', '주택'],
            'health': ['건강', '의료', '질병', '다이어트', '운동', '웰빙', '영양', '면역', '정신건강', '수면', '요가'],
            'lifestyle': ['라이프스타일', '여행', '음식', '패션', '뷰티', '인테리어', '취미', '문화', '예술', '영화', '음악', '독서'],
            'education': ['교육', '학습', '공부', '시험', '취업', '자격증', '어학', '프로그래밍', '코딩', '자기계발'],
            'social': ['사회', '정치', '환경', '기후변화', '인권', '복지', '봉사', '자원봉사', '기부'],
        }
        
        # 수익성 키워드 (기본 모델)
        self.revenue_keywords = {
            'high': ['구매', '쇼핑', '제품', '판매', '리뷰', '추천', '가격', '할인', '인기', '베스트', '화제', '최신'],
            'medium': ['방법', '팁', '가이드', '정보', '효과', '혜택', '비교', '장점', '단점', '선택', '등록', '신청'],
            'low': ['뜻', '의미', '근황', '사연', '이유', '이슈', '논란', '발언', '소식', '행사', '일정']
        }
        
        # 트렌드 분석 상태
        self.analyzed_trends = []
        self.history = {}  # 과거 트렌드 기록

    def analyze_trends(self, articles: List[Dict[str, Any]], job_id: str = None) -> List[Dict[str, Any]]:
        """
        뉴스 기사를 분석하여 추가 정보와 점수를 부여합니다.
        
        Args:
            articles (List[Dict[str, Any]]): 분석할 뉴스 기사 목록
            job_id (str, optional): 작업 ID
            
        Returns:
            List[Dict[str, Any]]: 분석된 뉴스 기사 목록
        """
        if not articles:
            return []
        
        # 성능 측정 시작
        if job_id:
            start_time = time.time()
        
        try:
            self.logger.info(f"트렌드 분석 시작: {len(articles)}개 기사")
            
            # 각 기사에 대한 추천 태그 생성
            for article in articles:
                # 태그 추출
                if 'keywords' in article:
                    # 상위 5개 키워드를 태그로 사용
                    article['recommended_tags'] = article['keywords'][:5]
                else:
                    article['recommended_tags'] = []
                
                # 카테고리 추정
                article['estimated_categories'] = self._estimate_categories(article)
                
                # 수익성 점수 계산
                article['monetization_score'] = self._calculate_monetization_score(article)
            
            # 수익성 점수로 정렬
            analyzed_articles = sorted(articles, key=lambda x: x.get('monetization_score', 0), reverse=True)
            
            # 상위 결과만 반환
            result = analyzed_articles[:self.max_results]
            
            # 성능 측정 및 메타데이터 기록
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
            
            self.logger.info(f"트렌드 분석 완료: 상위 {len(result)}개 기사 선정")
            return result
            
        except Exception as e:
            self.logger.error(f"트렌드 분석 중 오류 발생: {str(e)}")
            
            # 오류 발생 시에도 메타데이터 기록
            if job_id:
                end_time = time.time()
                track_performance(job_id, "trend_analysis", start_time, end_time)
                update_job_status(job_id, "failed", str(e))
            
            raise

    def _estimate_categories(self, article: Dict[str, Any]) -> List[str]:
        """
        뉴스 기사에 적합한 카테고리를 추정합니다.
        
        Args:
            article (Dict[str, Any]): 기사 정보
            
        Returns:
            List[str]: 추정된 카테고리 목록
        """
        # 기본 정보
        title = article.get('title', '')
        description = article.get('description', '')
        content = article.get('content', '')
        news_category = article.get('category', '')
        
        # 카테고리 점수
        category_scores = {category: 0 for category in self.categories}
        
        # 제목과 설명, 내용에서 카테고리 키워드 검색
        for category, keywords in self.categories.items():
            for keyword in keywords:
                keyword_lower = keyword.lower()
                
                # 제목에서 검색 (가중치 3)
                if keyword_lower in title.lower():
                    category_scores[category] += 3
                
                # 설명에서 검색 (가중치 2)
                if keyword_lower in description.lower():
                    category_scores[category] += 2
                
                # 내용에서 검색 (가중치 1)
                if content and keyword_lower in content.lower():
                    category_scores[category] += 1
        
        # 뉴스 카테고리 참고
        news_category = news_category.lower()
        if 'tech' in news_category or 'technology' in news_category:
            category_scores['tech'] += 2
        elif 'business' in news_category or 'finance' in news_category or 'economy' in news_category:
            category_scores['business'] += 2
        elif 'health' in news_category:
            category_scores['health'] += 2
        elif 'lifestyle' in news_category or 'entertainment' in news_category:
            category_scores['lifestyle'] += 2
        elif 'education' in news_category:
            category_scores['education'] += 2
        elif 'social' in news_category or 'society' in news_category or 'politics' in news_category:
            category_scores['social'] += 2
        
        # 점수가 1 이상인 카테고리만 선택
        selected_categories = [category for category, score in category_scores.items() if score > 0]
        
        # 카테고리가 없으면 가장 일반적인 카테고리 추가
        if not selected_categories:
            selected_categories = ['lifestyle']
        
        # 점수순으로 정렬
        selected_categories.sort(key=lambda category: category_scores[category], reverse=True)
        
        return selected_categories[:3]  # 최대 3개 카테고리 반환

    def _calculate_monetization_score(self, article: Dict[str, Any]) -> float:
        """
        뉴스 기사의 수익성 잠재력을 계산합니다.
        
        Args:
            article (Dict[str, Any]): 기사 정보
            
        Returns:
            float: 수익성 잠재력
        """
        # 기본 정보
        title = article.get('title', '')
        description = article.get('description', '')
        keywords = article.get('keywords', [])
        
        # 수익성 점수
        revenue_scores = {level: 0 for level in self.revenue_keywords}
        
        # 제목, 설명, 키워드에서 수익성 키워드 검색
        for level, level_keywords in self.revenue_keywords.items():
            for keyword in level_keywords:
                if keyword in title:
                    revenue_scores[level] += 3  # 제목에 있는 키워드는 가중치 높음
                if keyword in description:
                    revenue_scores[level] += 2  # 설명에 있는 키워드
                if any(keyword in k for k in keywords):
                    revenue_scores[level] += 1  # 키워드에 있는 경우
        
        # 추정 카테고리 기반 조정
        categories = self._estimate_categories(article)
        if 'tech' in categories or 'business' in categories:
            revenue_scores['high'] += 2
        elif 'health' in categories or 'lifestyle' in categories:
            revenue_scores['medium'] += 2
        
        # 가장 높은 점수의 수익성 결정
        if revenue_scores['high'] > revenue_scores['medium'] and revenue_scores['high'] > revenue_scores['low']:
            return 100.0
        elif revenue_scores['medium'] > revenue_scores['low']:
            return 70.0
        else:
            return 30.0

    def _generate_tags(self, article: Dict[str, Any], categories: List[str]) -> List[str]:
        """
        뉴스 기사에 적합한 태그를 생성합니다.
        
        Args:
            article (Dict[str, Any]): 기사 정보
            categories (List[str]): 추정된 카테고리
            
        Returns:
            List[str]: 추천 태그 목록
        """
        # 기본 정보
        title = article.get('title', '')
        keywords = article.get('keywords', [])
        
        # 기본 태그 (카테고리 + 키워드)
        tags = list(categories)  # 카테고리를 기본 태그로 추가
        
        # 키워드 추가
        for keyword in keywords:
            if len(keyword) > 1 and keyword not in tags:
                tags.append(keyword)
        
        # 카테고리별 관련 태그 추가
        for category in categories:
            if category in self.categories:
                # 카테고리 키워드 중 일부 추가 (최대 2개)
                category_keywords = self.categories[category]
                for keyword in random.sample(category_keywords, min(2, len(category_keywords))):
                    if keyword not in tags:
                        tags.append(keyword)
        
        # 중복 제거 및 정리
        unique_tags = []
        for tag in tags:
            tag = tag.strip()
            if tag and tag not in unique_tags:
                unique_tags.append(tag)
        
        return unique_tags[:10]  # 최대 10개 태그 반환
    
    def _generate_summary(self, article: Dict[str, Any]) -> str:
        """
        뉴스 기사의 간단한 요약을 생성합니다.
        
        Args:
            article (Dict[str, Any]): 기사 정보
            
        Returns:
            str: 기사 요약
        """
        title = article.get('title', '')
        description = article.get('description', '')
        source = article.get('source', {}).get('name', '')
        published_at = article.get('published_at', '')
        
        # 날짜 포맷 변경
        try:
            pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            formatted_date = pub_date.strftime('%Y년 %m월 %d일')
        except:
            formatted_date = published_at
        
        return f"{title}\n\n{description}\n\n출처: {source}, {formatted_date}"
    
    def _suggest_blog_topic(self, article: Dict[str, Any], categories: List[str]) -> str:
        """
        뉴스 기사를 기반으로 블로그 주제를 제안합니다.
        
        Args:
            article (Dict[str, Any]): 기사 정보
            categories (List[str]): 추정된 카테고리
            
        Returns:
            str: 제안된 블로그 주제
        """
        title = article.get('title', '')
        keywords = article.get('keywords', [])
        
        # 제목에서 블로그 주제 추출 시도
        topic = title
        
        # 카테고리에 따른 주제 형식 적용
        primary_category = categories[0] if categories else 'general'
        
        if primary_category == 'tech':
            topic = f"최신 기술 트렌드: {title}"
        elif primary_category == 'business':
            topic = f"비즈니스 인사이트: {title}"
        elif primary_category == 'health':
            topic = f"건강 가이드: {title}"
        elif primary_category == 'lifestyle':
            topic = f"라이프스타일 트렌드: {title}"
        elif primary_category == 'education':
            topic = f"교육 및 학습: {title}"
        elif primary_category == 'social':
            topic = f"사회 이슈: {title}"
        
        return topic 