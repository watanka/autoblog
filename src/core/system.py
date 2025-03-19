#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
블로그 자동화 시스템의 핵심 시스템 구현
"""

import os
import json
import logging
from datetime import datetime
import uuid  # 고유 작업 ID 생성을 위해 추가
from typing import List, Dict, Any, Optional

from src.core.interfaces import TrendParser, TrendAnalyzer, ContentGenerator, ContentFormatter, Publisher, DataStorage
from src.storage import JsonFileStorage


class BlogAutomationSystem:
    """블로그 자동화 시스템 메인 클래스"""
    
    def __init__(
        self,
        trend_parsers: List[TrendParser],
        trend_analyzer: TrendAnalyzer,
        content_generator: ContentGenerator,
        content_formatter: ContentFormatter,
        publishers: Dict[str, Publisher],
        config: Dict[str, Any]
    ):
        """
        블로그 자동화 시스템을 초기화합니다.
        
        Args:
            trend_parser (TrendParser): 뉴스 기사 파싱 구현체
            trend_analyzer (TrendAnalyzer): 뉴스 기사 분석 구현체
            content_generator (ContentGenerator): 콘텐츠 생성 구현체
            content_formatter (ContentFormatter): 콘텐츠 포맷팅 구현체
            publishers (Dict[str, Publisher]): 플랫폼별 게시 구현체
            config (Dict[str, Any]): 시스템 설정
        """
        self.logger = logging.getLogger('autoblog.system')
        
        # 모듈 초기화
        self.trend_parsers = trend_parsers
        self.trend_analyzer = trend_analyzer
        self.content_generator = content_generator
        self.content_formatter = content_formatter
        self.publishers = publishers
        
        # 설정
        self.config = config
        self.data_dir = config.get('data_dir', 'data')
        
        # 데이터 스토리지 초기화
        self.storage = JsonFileStorage(self.data_dir)
        
        # 현재 작업의 고유 ID
        self.job_id = self._generate_job_id()
        
        self.logger.info("BlogAutomationSystem 초기화 완료")
    
    def _generate_job_id(self) -> str:
        """
        현재 작업을 위한 고유 ID를 생성합니다.
        
        Returns:
            str: 고유 작업 ID
        """
        # UUID 생성 (타임스탬프도 함께 사용하여 순서 보장)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # UUID의 첫 8자리만 사용
        job_id = f"{timestamp}_{unique_id}"
        
        # 메타데이터 파일 생성
        self._create_job_metadata(job_id)
        
        return job_id
    
    def _create_job_metadata(self, job_id: str) -> None:
        """
        작업 메타데이터 파일을 생성합니다.
        
        Args:
            job_id: 작업 고유 ID
        """
        metadata = {
            'job_id': job_id,
            'started_at': datetime.now().isoformat(),
            'status': 'started',
            'files': {
                'trends': None,
                'contents': None,
                'publishing_results': None
            }
        }
        
        self.storage.create_metadata(job_id, metadata)
    
    def _update_job_metadata(self, file_type: str, file_path: str) -> None:
        """
        작업 메타데이터를 업데이트합니다.
        
        Args:
            file_type: 파일 유형 ('trends', 'contents', 'publishing_results')
            file_path: 파일 경로
        """
        if not self.job_id:
            return
        
        # 파일 경로 업데이트
        self.storage.update_metadata(self.job_id, f"files.{file_type}", file_path)
        
        # 상태 업데이트 (publishing_results가 설정되면 완료 상태로 변경)
        if file_type == 'publishing_results':
            self.storage.update_metadata(self.job_id, "status", "completed")
    
    def discover_trends(self) -> List[Dict[str, Any]]:
        """뉴스 기사를 수집합니다."""
        self.logger.info("트렌드 발견 시작")
        
        articles = []
        for parser in self.trend_parsers:
            articles.extend(parser.get_trends(job_id=self.job_id))
        
        if not articles:
            self.logger.warning("수집된 뉴스 기사가 없습니다.")
        else:
            self.logger.info(f"{len(articles)}개 뉴스 기사 수집됨")
        
        return articles
    
    def analyze_trends(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """수집된 뉴스 기사를 분석합니다."""
        if not articles:
            self.logger.warning("분석할 뉴스 기사가 없습니다.")
            return []
        
        self.logger.info("트렌드 분석 시작")
        analyzed_articles = self.trend_analyzer.analyze_trends(articles, job_id=self.job_id)
        self.logger.info(f"트렌드 분석 완료: {len(analyzed_articles)}개 기사 선정됨")
        
        return analyzed_articles
    
    def generate_contents(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """선정된 뉴스 기사를 기반으로 블로그 콘텐츠를 생성합니다."""
        if not articles:
            self.logger.warning("콘텐츠를 생성할 뉴스 기사가 없습니다.")
            return []
        
        self.logger.info(f"콘텐츠 생성 시작: {len(articles)}개 기사")
        contents = []
        
        for idx, article in enumerate(articles):
            self.logger.info(f"[{idx+1}/{len(articles)}] 기사 '{article.get('title', '')[:30]}...' 콘텐츠 생성 중")
            content = self.content_generator.generate_content(article, job_id=self.job_id)
            
            # 포맷팅
            formatted_content = self.content_formatter.format_content(content, )
            contents.append(formatted_content)
        
        self.logger.info(f"콘텐츠 생성 완료: {len(contents)}개 콘텐츠")
        return contents
    
    def publish_contents(self, contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """생성된 콘텐츠를 블로그에 게시합니다."""
        if not contents:
            self.logger.warning("게시할 콘텐츠가 없습니다.")
            return []
        
        self.logger.info(f"콘텐츠 게시 시작: {len(contents)}개 콘텐츠")
        results = []
        
        for platform_name, publisher in self.publishers.items():
            self.logger.info(f"'{platform_name}' 플랫폼에 게시 중...")
            result = publisher.publish(contents, job_id=self.job_id)
            results.append(result)
            
            self.logger.info(f"'{platform_name}' 게시 결과: {result.get('status')} - {result.get('message')}")
        
        self.logger.info("콘텐츠 게시 완료")
        return results
    
    def save_trends_data(self, articles: List[Dict[str, Any]]) -> str:
        """
        트렌드 데이터를 파일로 저장합니다.
        
        Args:
            articles: 저장할 트렌드 데이터
            
        Returns:
            str: 저장된 파일 경로
        """
        file_path = f"trends/trends_{self.job_id}.json"
        full_path = self.storage.save_data(articles, file_path, self.job_id)
        
        # 메타데이터 업데이트
        relative_path = os.path.relpath(full_path, self.data_dir)
        self._update_job_metadata('trends', relative_path)
        
        return full_path
    
    def save_contents_data(self, contents: List[Dict[str, Any]]) -> str:
        """
        콘텐츠 데이터를 파일로 저장합니다.
        
        Args:
            contents: 저장할 콘텐츠 데이터
            
        Returns:
            str: 저장된 파일 경로
        """
        file_path = f"contents/contents_{{job_id}}.json"
        full_path = self.storage.save_data(contents, file_path, self.job_id)
        
        # 메타데이터 업데이트
        relative_path = os.path.relpath(full_path, self.data_dir)
        self._update_job_metadata('contents', relative_path)
        
        return full_path
    
    def save_publishing_results(self, results: List[Dict[str, Any]]) -> str:
        """
        게시 결과 데이터를 파일로 저장합니다.
        
        Args:
            results: 저장할 게시 결과 데이터
            
        Returns:
            str: 저장된 파일 경로
        """
        file_path = f"results/publishing_results_{{job_id}}.json"
        full_path = self.storage.save_data(results, file_path, self.job_id)
        
        # 메타데이터 업데이트
        relative_path = os.path.relpath(full_path, self.data_dir)
        self._update_job_metadata('publishing_results', relative_path)
        
        return full_path
    
    def load_trends_data(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        저장된 트렌드 데이터를 로드합니다.
        
        Args:
            job_id: 로드할 작업 ID. None이면 현재 작업 또는 최신 작업의 데이터를 로드합니다.
            
        Returns:
            List[Dict[str, Any]]: 로드된 트렌드 데이터
        """
        try:
            # 사용할 작업 ID 결정
            used_job_id = job_id or self.job_id
            
            # 데이터 로드
            trends = self.storage.load_data("trends/trends_{job_id}.json", used_job_id)
            
            self.logger.info(f"트렌드 데이터 로드 완료: {len(trends)}개 항목")
            return trends
        except Exception as e:
            self.logger.error(f"트렌드 데이터 로드 중 오류 발생: {str(e)}")
            return []
    
    def load_contents_data(self, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        저장된 콘텐츠 데이터를 로드합니다.
        
        Args:
            job_id: 로드할 작업 ID. None이면 현재 작업 또는 최신 작업의 데이터를 로드합니다.
            
        Returns:
            List[Dict[str, Any]]: 로드된 콘텐츠 데이터
        """
        try:
            # 사용할 작업 ID 결정
            used_job_id = job_id or self.job_id
            
            # 데이터 로드
            contents = self.storage.load_data("contents/contents_{job_id}.json", used_job_id)
            
            self.logger.info(f"콘텐츠 데이터 로드 완료: {len(contents)}개 항목")
            return contents
        except Exception as e:
            self.logger.error(f"콘텐츠 데이터 로드 중 오류 발생: {str(e)}")
            return []
