#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Docusaurus 형식의 콘텐츠 포맷터 구현
"""

import logging
import re
import os
import string
from datetime import datetime
from typing import Dict, Any, List, Optional
import unicodedata

from src.core.interfaces import ContentFormatter

class DocusaurusFormatter(ContentFormatter):
    """Docusaurus 형식의 콘텐츠 포맷터 구현"""
    
    def __init__(self, templates: Dict[str, str]):
        """
        Docusaurus 포맷터를 초기화합니다.
        
        Args:
            templates (Dict[str, str]): 사용 가능한 템플릿 딕셔너리
        """
        self.logger = logging.getLogger('autoblog.content.formatter')
        self.templates = templates
        self.logger.debug(f"Docusaurus 포맷터 초기화 완료, {len(templates)} 템플릿 로드됨")
    
    def format_content(self, content: Dict[str, Any], template_name: str='blog') -> str:
        """
        생성된 콘텐츠를 Docusaurus 블로그 포스트 형식으로 포맷팅합니다.
        
        Args:
            content (Dict[str, Any]): 포맷팅할 콘텐츠 데이터
            template_name (str): 사용할 템플릿 이름
            
        Returns:
            str: 포맷팅된 콘텐츠 문자열
        """
        if template_name not in self.templates:
            self.logger.warning(f"템플릿 '{template_name}'을 찾을 수 없습니다. 기본 Docusaurus 포맷으로 포맷팅합니다.")
            return self._default_format(content)
        
        template = self.templates[template_name]
        self.logger.debug(f"'{template_name}' 템플릿을 사용하여 Docusaurus 포맷팅 시작")
        
        # slug 생성
        slug = self._generate_slug(content.get('title', ''))
        
        # 태그 생성
        tags = self._get_tags(content)
        # 단일 태그용 형식
        tag = tags.split(', ')[0] if tags else 'auto-generated'
        
        # 템플릿 변수 대체
        formatted_content = template
        formatted_content = formatted_content.replace('{{slug}}', slug)
        formatted_content = formatted_content.replace('{{title}}', f'"{content.get("title", "제목 없음")}"')
        formatted_content = formatted_content.replace('{{tags}}', tags)
        formatted_content = formatted_content.replace('{{tag}}', tag)
        formatted_content = formatted_content.replace('{{content}}', content.get('content', ''))
        formatted_content = formatted_content.replace('{{date}}', datetime.now().strftime('%Y-%m-%d'))
        
        # Docusaurus 특화: 저자 정보
        authors = self._get_authors(content)
        # 리스트 형식 제거
        authors = authors.replace('[', '').replace(']', '')
        formatted_content = formatted_content.replace('{{authors}}', authors)
        
        # Docusaurus 특화: 이미지 경로 URL 수정
        formatted_content = self._fix_image_paths(formatted_content)
        
        self.logger.debug("Docusaurus 콘텐츠 포맷팅 완료")
        return formatted_content
    
    def _default_format(self, content: Dict[str, Any]) -> str:
        """
        기본 Docusaurus 형식으로 포맷팅합니다.
        
        Args:
            content (Dict[str, Any]): 포맷팅할 콘텐츠 데이터
            
        Returns:
            str: 포맷팅된 Docusaurus 문자열
        """
        title = content.get('title', '제목 없음')
        main_content = content.get('content', '')
        slug = self._generate_slug(title)
        
        # 태그 생성
        tags = self._get_tags(content)
        
        # 기본 Docusaurus 프론트매터
        formatted = "---\n"
        formatted += f"slug: {slug}\n"
        formatted += f'title: "{title}"\n'
        formatted += "authors: autoblog\n"
        formatted += f"tags: [{tags}]\n"
        formatted += "---\n\n"
        
        # 본문 추가
        formatted += main_content
        
        return formatted
    
    def _generate_slug(self, title: str) -> str:
        """
        제목에서 Docusaurus에 적합한 slug를 생성합니다.
        
        Args:
            title (str): 블로그 제목
            
        Returns:
            str: 생성된 slug
        """
        # 날짜 프리픽스 생성
        date_prefix = datetime.now().strftime('%Y-%m-%d')
        
        # 한글 포함 여부 확인
        has_korean = any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in title)
        
        if has_korean:
            # 영문자와 숫자만 추출
            english_nums = re.sub(r'[^\w\s]', '', re.sub(r'[^\x00-\x7F]+', '', title.lower()))
            
            # 영문자나 숫자가 있으면 그것으로 슬러그 생성
            if english_nums.strip():
                slug_text = re.sub(r'\s+', '-', english_nums.strip())
            else:
                # 영문자나 숫자가 없으면 'post' + 타임스탬프로 대체
                timestamp = datetime.now().strftime("%H%M%S")
                slug_text = f"post-{timestamp}"
        else:
            # 영문 제목은 기존 방식대로 처리
            slug_text = re.sub(r'[^\w\s-]', '', title.lower())
            slug_text = re.sub(r'[\s_-]+', '-', slug_text)
            slug_text = re.sub(r'^-+|-+$', '', slug_text)
        
        return f"{date_prefix}-{slug_text}"
    
    def _get_tags(self, content: Dict[str, Any]) -> str:
        """
        콘텐츠에서 태그를 추출합니다.
        
        Args:
            content (Dict[str, Any]): 콘텐츠 데이터
            
        Returns:
            str: 쉼표로 구분된 태그 문자열
        """
        # 기사 데이터에서 태그 추출
        article_data = content.get('article_data', {})
        
        # 기사에 이미 태그나 카테고리가 있으면 사용
        tags = article_data.get('recommended_tags', [])
        
        if not tags and 'estimated_categories' in article_data:
            tags = article_data.get('estimated_categories', [])
        
        # 태그가 없으면 제목에서 키워드 추출
        if not tags:
            title = content.get('title', '')
            # 간단한 키워드 추출 (3글자 이상 단어)
            words = re.findall(r'\b\w{3,}\b', title.lower())
            # 상위 3개 단어를 태그로 사용
            tags = list(set(words))[:3]
        
        # 태그 처리: 특수문자 제거, 공백을 하이픈으로 변경
        processed_tags = []
        for tag in tags:
            if isinstance(tag, str):  # 태그가 문자열인지 확인
                # 공백을 하이픈으로 변경, 소문자로 변환
                processed_tag = tag.lower().strip()
                processed_tag = re.sub(r'\s+', '-', processed_tag)
                # 특수문자 제거
                processed_tag = re.sub(r'[^\w\-]', '', processed_tag)
                if processed_tag:  # 빈 문자열이 아니면 추가
                    processed_tags.append(processed_tag)
        
        # 리스트를 쉼표로 구분된 문자열로 변환
        return ', '.join(processed_tags)
    
    def _get_authors(self, content: Dict[str, Any]) -> str:
        """
        콘텐츠 작성자 정보를 가져옵니다.
        
        Args:
            content (Dict[str, Any]): 콘텐츠 데이터
            
        Returns:
            str: 작성자 이름(들)
        """
        # 기본 작성자는 'autoblog'
        authors = content.get('authors', 'autoblog')
        
        if isinstance(authors, str):
            return authors
        elif isinstance(authors, list):
            # 리스트의 첫 번째 항목만 반환
            return authors[0] if authors else 'autoblog'
        else:
            return 'autoblog'
    
    def _fix_image_paths(self, content: str) -> str:
        """
        마크다운 내 이미지 경로를 Docusaurus에 맞게 수정합니다.
        
        Args:
            content (str): 원본 콘텐츠
            
        Returns:
            str: 이미지 경로가 수정된 콘텐츠
        """
        # Docusaurus에서는 이미지가 static/img/ 경로에 있어야 함
        # ![alt text](image.jpg) -> ![alt text](/img/image.jpg)
        content = re.sub(
            r'!\[(.*?)\]\((?!https?://)(.*?)\)',
            r'![\1](/img/\2)',
            content
        )
        
        return content 