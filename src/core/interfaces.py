#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
블로그 자동화 시스템의 핵심 인터페이스 정의
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class TrendParser(ABC):
    """뉴스 기사 및 트렌드 파싱을 위한 인터페이스"""
    
    @abstractmethod
    def get_trends(self) -> List[Dict[str, Any]]:
        """
        현재 인기 있는 뉴스 기사를 가져옵니다.
        
        Returns:
            List[Dict[str, Any]]: 파싱된 뉴스 기사 목록
            각 기사는 최소한 'title', 'description', 'url' 키를 포함해야 합니다.
        """
        pass


class TrendAnalyzer(ABC):
    """트렌드 분석을 위한 인터페이스"""
    
    @abstractmethod
    def analyze_trends(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        뉴스 기사 목록을 분석하여 수익성, 인기도 등의 정보를 추가합니다.
        
        Args:
            articles (List[Dict[str, Any]]): 분석할 뉴스 기사 목록
            
        Returns:
            List[Dict[str, Any]]: 분석된 뉴스 기사 목록
            각 기사는 원본 데이터에 'popularity_score', 'revenue_potential', 
            'estimated_categories', 'recommended_tags' 등이 추가됩니다.
        """
        pass


class ContentGenerator(ABC):
    """콘텐츠 생성을 위한 인터페이스"""
    
    @abstractmethod
    def generate_content(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        주어진 뉴스 기사에 대한 블로그 콘텐츠를 생성합니다.
        
        Args:
            article (Dict[str, Any]): 콘텐츠를 생성할 뉴스 기사 정보
            
        Returns:
            Dict[str, Any]: 생성된 콘텐츠 (최소한 'title'과 'content' 키를 포함)
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, article: Dict[str, Any]) -> float:
        """
        주어진 뉴스 기사에 대한 콘텐츠 생성 비용을 예측합니다.
        
        Args:
            article (Dict[str, Any]): 콘텐츠를 생성할 뉴스 기사 정보
            
        Returns:
            float: 예상 비용 (달러)
        """
        pass


class ContentFormatter(ABC):
    """콘텐츠 포맷팅을 위한 인터페이스"""
    
    @abstractmethod
    def format_content(self, content: Dict[str, Any], template_name: str) -> str:
        """
        생성된 콘텐츠를 지정된 템플릿에 맞게 포맷팅합니다.
        
        Args:
            content (Dict[str, Any]): 포맷팅할 콘텐츠 데이터
            template_name (str): 사용할 템플릿 이름
            
        Returns:
            str: 포맷팅된 콘텐츠 문자열
        """
        pass


class Publisher(ABC):
    """콘텐츠 게시를 위한 인터페이스"""
    
    @abstractmethod
    def publish(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        포맷팅된 콘텐츠를 게시합니다.
        
        Args:
            content (Dict[str, Any]): 게시할 콘텐츠 데이터
            
        Returns:
            Dict[str, Any]: 게시 결과 정보 (최소한 'id'나 'url' 등의 식별자 포함)
        """
        pass


class DataStorage(ABC):
    """데이터 저장 및 로드를 위한 인터페이스"""
    
    @abstractmethod
    def save_data(self, data: Any, path: str, job_id: Optional[str] = None) -> str:
        """
        데이터를 지정된 경로에 저장합니다.
        
        Args:
            data (Any): 저장할 데이터
            path (str): 저장 경로
            job_id (Optional[str]): 작업 ID (고유 식별자)
            
        Returns:
            str: 데이터가 저장된 실제 경로
        """
        pass
    
    @abstractmethod
    def load_data(self, path: str, job_id: Optional[str] = None) -> Any:
        """
        지정된 경로에서 데이터를 로드합니다.
        
        Args:
            path (str): 로드할 데이터 경로
            job_id (Optional[str]): 작업 ID (고유 식별자)
            
        Returns:
            Any: 로드된 데이터
        """
        pass
    
    @abstractmethod
    def create_metadata(self, job_id: str, metadata: Dict[str, Any]) -> str:
        """
        작업 메타데이터 파일을 생성합니다.
        
        Args:
            job_id (str): 작업 ID
            metadata (Dict[str, Any]): 메타데이터
            
        Returns:
            str: 메타데이터 파일 경로
        """
        pass
    
    @abstractmethod
    def update_metadata(self, job_id: str, key: str, value: Any) -> bool:
        """
        작업 메타데이터를 업데이트합니다.
        
        Args:
            job_id (str): 작업 ID
            key (str): 업데이트할 키
            value (Any): 설정할 값
            
        Returns:
            bool: 업데이트 성공 여부
        """
        pass
    
    @abstractmethod
    def find_latest_job(self, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        가장 최근 작업의 메타데이터를 찾습니다.
        
        Args:
            status (Optional[str]): 찾을 작업 상태 (None이면 모든 상태)
            
        Returns:
            Optional[Dict[str, Any]]: 메타데이터 딕셔너리, 없으면 None
        """
        pass
